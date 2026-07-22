"""Extração de dados de boletos Sicoob a partir do texto do PDF (pdfplumber).

Layouts reais do Sicoob costumam sair do pdfplumber em formato tabular:
uma linha só de rótulos ("Nome do pagador Número do Documento ...") seguida
de uma linha com os valores. Por isso a extração ignora linhas compostas
apenas de rótulos conhecidos e corta o nome no primeiro token de dado
(data, valor, CPF/CNPJ, número composto).

A extração de texto é best-effort: qualquer campo que não bater com a
linha digitável vira divergência e manda o boleto para revisão manual.
"""

import io
import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import pdfplumber

from .linha_digitavel import RE_LINHA_FORMATADA

logger = logging.getLogger("camf.extracao")

RE_LINHA_CRUA = re.compile(r"\d{47}")
RE_CPF = re.compile(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}")
RE_CNPJ = re.compile(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}")
RE_CPF_CNPJ = re.compile(rf"(?:{RE_CNPJ.pattern})|(?:{RE_CPF.pattern})")
RE_DATA = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")
RE_VALOR = re.compile(r"\b(\d{1,3}(?:\.\d{3})*,\d{2})\b")
RE_CEP = re.compile(r"\b(\d{5})-?(\d{3})\b")
RE_MUNICIPIO_UF = re.compile(r"([A-Za-zÀ-ÿ'.\s]+?)\s*[-/]\s*([A-Z]{2})\b")
# Só hífen: com barra a regex casaria com pedaços de data ('01/06')
RE_NUMERO_COMPOSTO = re.compile(r"\b(\d+-\d+)\b")
# Primeiro token que claramente é dado (e não parte de um nome)
RE_TOKEN_DADO = re.compile(
    r"\d{2}/\d{2}/\d{4}"
    r"|\d{1,3}(?:\.\d{3})*,\d{2}"
    rf"|(?:{RE_CPF_CNPJ.pattern})"
    r"|\b\d+[-/]\d+\b"
)
RE_SUFIXO_ROTULO_DOC = re.compile(r"(CPF\s*/\s*CNPJ|CPF|CNPJ)[\s.:/-]*$", re.IGNORECASE)

MARCADORES_BOLETO = ("SICOOB", "FICHA DE COMPENSAÇÃO", "FICHA DE COMPENSACAO")

# Rótulos que aparecem nos boletos Sicoob; linhas compostas só por eles são
# cabeçalhos de tabela, nunca valores. (sem acentos, minúsculas)
ROTULOS_CONHECIDOS = [
    "nome do pagador", "pagador final", "pagador", "beneficiario final", "beneficiario",
    "numero do documento", "nº do documento", "no do documento", "num do documento",
    "cpf/cnpj do pagador", "cpf/cnpj", "cpf", "cnpj",
    "endereco do pagador", "endereco", "bairro", "municipio", "cidade", "uf", "cep",
    "data de vencimento", "vencimento", "data do documento", "data de emissao",
    "data de processamento", "data processamento",
    "valor do documento", "valor cobrado", "valor",
    "nosso numero", "especie doc", "especie moeda", "especie", "carteira",
    "agencia/codigo beneficiario", "agencia / codigo beneficiario",
    "agencia/codigo do beneficiario", "codigo do beneficiario", "codigo beneficiario",
    "agencia", "uso do banco", "aceite", "quantidade", "moeda", "parcela",
    "desconto", "abatimento", "juros", "multa", "outras deducoes", "outros acrescimos",
    "local de pagamento", "sacador", "avalista", "autenticacao mecanica",
    "ficha de compensacao", "recibo do pagador", "instrucoes",
    "texto de responsabilidade do beneficiario", "corte na linha pontilhada",
    "pagavel preferencialmente", "cooperativa de credito", "sisbr",
]
_ROTULOS_ORDENADOS = sorted(ROTULOS_CONHECIDOS, key=len, reverse=True)


@dataclass
class DadosPagina:
    linha_digitavel_bruta: str
    pagador_nome: str | None = None
    pagador_cpf_cnpj: str | None = None
    endereco: str | None = None
    bairro: str | None = None
    municipio: str | None = None
    uf: str | None = None
    cep: str | None = None
    num_documento: str | None = None
    nosso_numero: str | None = None
    especie: str | None = None
    carteira: str | None = None
    data_emissao: date | None = None
    vencimento: date | None = None
    valor: Decimal | None = None
    beneficiario_nome: str | None = None
    beneficiario_cnpj: str | None = None


def extrair_textos_paginas(conteudo: bytes) -> list[str]:
    """Extrai o texto de cada página do PDF. Página ilegível vira string vazia."""
    with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
        textos = []
        for pagina in pdf.pages:
            try:
                textos.append(pagina.extract_text() or "")
            except Exception:  # página ilegível não derruba o arquivo
                logger.warning("Falha ao extrair texto de uma página", exc_info=True)
                textos.append("")
        return textos


def parece_boleto(texto: str) -> bool:
    """Página sem linha digitável mas com marcadores Sicoob: possível falha de parsing."""
    maiusculo = texto.upper()
    return any(m in maiusculo for m in MARCADORES_BOLETO)


def localizar_linha_digitavel(texto: str) -> str | None:
    m = RE_LINHA_FORMATADA.search(texto)
    if m:
        return m.group(0)
    m = RE_LINHA_CRUA.search(re.sub(r"[.\s]", "", texto))
    return m.group(0) if m else None


def _sem_acentos_minusculo(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()


def eh_linha_rotulo(linha: str) -> bool:
    """True se a linha é composta apenas por rótulos de campos do boleto."""
    txt = _sem_acentos_minusculo(linha)
    for rotulo in _ROTULOS_ORDENADOS:
        txt = txt.replace(rotulo, " ")
    return len(re.sub(r"[^a-z]", "", txt)) <= 2


# Palavras que compõem rótulos de campos — nunca fazem parte de um nome real.
# Um nome candidato que sobra só com essas palavras é, na verdade, um rótulo.
_STOPWORDS_ROTULO = {"do", "da", "de", "dos", "das", "no", "na", "e"}
for _r in ROTULOS_CONHECIDOS:
    _STOPWORDS_ROTULO.update(_sem_acentos_minusculo(_r).split())


def _token_normalizado(token: str) -> str:
    return _sem_acentos_minusculo(re.sub(r"[^A-Za-zÀ-ÿ]", "", token))


def _limpar_nome(nome: str) -> str:
    """Remove rótulos que grudam no começo do nome (layout tabular)."""
    tokens = nome.split()
    i = 0
    while i < len(tokens) and _token_normalizado(tokens[i]) in _STOPWORDS_ROTULO:
        i += 1
    return " ".join(tokens[i:]).strip(" -:.,|")


def _nome_na_linha(linha: str) -> str | None:
    """Extrai o nome do início da linha, cortando no primeiro token de dado.

    Ex.: 'MARIA OLIVEIRA 7-02 529.982.247-25 10/08/2026' -> 'MARIA OLIVEIRA'
    """
    m = RE_TOKEN_DADO.search(linha)
    nome = linha[: m.start()] if m else linha
    nome = RE_SUFIXO_ROTULO_DOC.sub("", nome.strip())
    return nome.strip(" -:.,|") or None


def _nome_valido(bruto: str | None) -> str | None:
    """Valida um nome candidato: rejeita rótulos, devolve o nome limpo ou None.

    Garante que texto como 'Nome do pagador Número do Documento' — que é só
    uma sequência de rótulos — nunca seja aceito como nome de pagador.
    """
    if not bruto:
        return None
    limpo = _limpar_nome(bruto)
    letras = re.sub(r"[^A-Za-zÀ-ÿ]", "", limpo)
    if len(letras) < 3 or eh_linha_rotulo(limpo):
        return None
    return limpo


def _parse_data(texto: str | None) -> date | None:
    if not texto:
        return None
    try:
        return datetime.strptime(texto, "%d/%m/%Y").date()
    except ValueError:
        return None


def parse_valor_brl(texto: str | None) -> Decimal | None:
    """'10.985,00' -> Decimal('10985.00')"""
    if not texto:
        return None
    try:
        return Decimal(texto.replace(".", "").replace(",", "."))
    except InvalidOperation:
        return None


# Rótulos cujo valor é uma data — usados p/ posicionar colunas no layout tabular
RE_ROTULOS_COM_DATA = re.compile(
    r"Data d[eo] Documento|Data de Emiss[ãa]o|Data de Processamento|Vencimento",
    re.IGNORECASE,
)


def _data_apos_rotulo(texto: str, padrao_rotulo: str) -> date | None:
    """Data associada a um rótulo, cobrindo os dois layouts do Sicoob.

    Inline ('Vencimento 10/08/2026'): primeira data após o rótulo na mesma linha.
    Tabular (linha de rótulos + linha de valores): conta quantos rótulos de data
    aparecem antes na linha de cabeçalhos e pega a data de mesma posição na
    linha de valores seguinte.
    """
    for m in re.finditer(padrao_rotulo, texto, re.IGNORECASE):
        fim_linha = texto.find("\n", m.end())
        if fim_linha == -1:
            fim_linha = len(texto)
        m_data = RE_DATA.search(texto[m.end(): fim_linha])
        if m_data:
            return _parse_data(m_data.group(1))
        inicio_linha = texto.rfind("\n", 0, m.start()) + 1
        posicao = len(RE_ROTULOS_COM_DATA.findall(texto[inicio_linha: m.start()]))
        proximas = [l for l in texto[fim_linha:].splitlines() if l.strip()]
        if proximas:
            datas = RE_DATA.findall(proximas[0])
            if len(datas) > posicao:
                return _parse_data(datas[posicao])
    return None


def _contem_linha_digitavel(linha: str) -> bool:
    return bool(
        RE_LINHA_FORMATADA.search(linha)
        or RE_LINHA_CRUA.search(re.sub(r"[.\s]", "", linha))
    )


def _apos_rotulo(texto: str, rotulos: list[str], padrao: re.Pattern, janela: int = 140) -> str | None:
    """Procura `padrao` numa janela de texto logo após um dos rótulos."""
    for rotulo in rotulos:
        for m in re.finditer(rotulo, texto, re.IGNORECASE):
            trecho = texto[m.end(): m.end() + janela]
            achado = padrao.search(trecho)
            if achado:
                return achado.group(0)
    return None


def _bloco_pagador(texto: str) -> list[str]:
    """Linhas do bloco 'Pagador' (janela após o primeiro rótulo de pagador)."""
    m = re.search(r"(?:Nome do\s+)?Pagador\b[.:\s]*", texto, re.IGNORECASE)
    if not m:
        return []
    trecho = texto[m.end(): m.end() + 600]
    corte = re.search(
        r"(Sacador|Avalista|Autentica|C[oó]digo de baixa|Benefici[áa]rio Final"
        r"|Ficha de Compensa|Instru[çc][õo]es)",
        trecho,
        re.IGNORECASE,
    )
    if corte:
        trecho = trecho[: corte.start()]
    return [linha.strip() for linha in trecho.splitlines() if linha.strip()]


def extrair_dados_pagina(texto: str) -> DadosPagina | None:
    """Retorna os dados da página ou None quando não há linha digitável."""
    linha = localizar_linha_digitavel(texto)
    if linha is None:
        return None

    dados = DadosPagina(linha_digitavel_bruta=linha)

    dados.vencimento = _data_apos_rotulo(texto, r"(?:Data de\s+)?Vencimento")
    dados.data_emissao = _data_apos_rotulo(
        texto, r"Data d[eo] Documento|Data de Emiss[ãa]o"
    )
    dados.valor = parse_valor_brl(
        _apos_rotulo(texto, [r"\(=\)\s*Valor do Documento", r"Valor do Documento"], RE_VALOR)
    )
    dados.nosso_numero = _apos_rotulo(
        texto, [r"Nosso N[úu]mero"], RE_NUMERO_COMPOSTO, janela=60
    )
    dados.num_documento = _apos_rotulo(
        texto,
        [r"N[º°.]?\s*do Documento", r"N[úu]mero do Documento"],
        RE_NUMERO_COMPOSTO,
        janela=60,
    )
    dados.especie = _apos_rotulo(
        texto, [r"Esp[ée]cie Doc\.?", r"Esp[ée]cie DOC"], re.compile(r"\b[A-Z]{2,4}\b"), janela=30
    )
    dados.carteira = _apos_rotulo(texto, [r"Carteira"], re.compile(r"\b\d{1,3}\b"), janela=30)

    # Beneficiário: nome + CNPJ na mesma janela
    m_benef = re.search(r"Benefici[áa]rio\b[:\s]*", texto, re.IGNORECASE)
    if m_benef:
        trecho = texto[m_benef.end(): m_benef.end() + 200]
        m_doc = RE_CPF_CNPJ.search(trecho)
        if m_doc:
            dados.beneficiario_cnpj = m_doc.group(0)
            nome = trecho[: m_doc.start()]
        else:
            nome = trecho.splitlines()[0] if trecho.splitlines() else ""
        nome = RE_SUFIXO_ROTULO_DOC.sub("", nome.strip())
        dados.beneficiario_nome = (nome.strip(" -:").splitlines() or [""])[0].strip() or None

    _extrair_pagador(texto, dados)
    return dados


def _extrair_pagador(texto: str, dados: DadosPagina) -> None:
    linhas = _bloco_pagador(texto)
    if not linhas:
        return
    beneficiario_doc = re.sub(r"\D", "", dados.beneficiario_cnpj or "")

    # Linhas de conteúdo: ignora cabeçalhos compostos só por rótulos
    conteudo = [l for l in linhas if not eh_linha_rotulo(l)]

    idx_nome = None
    for i, linha in enumerate(conteudo):
        nome = _nome_valido(_nome_na_linha(linha))
        if nome:
            dados.pagador_nome = nome
            idx_nome = i
            break

    # Documento do pagador: primeiro CPF/CNPJ do bloco que não seja o do
    # beneficiário (a linha digitável é excluída: seus dígitos enganam a regex)
    for linha in linhas:
        if _contem_linha_digitavel(linha):
            continue
        doc_achado = None
        for m_doc in RE_CPF_CNPJ.finditer(linha):
            if re.sub(r"\D", "", m_doc.group(0)) != beneficiario_doc:
                doc_achado = m_doc.group(0)
                break
        if doc_achado:
            dados.pagador_cpf_cnpj = doc_achado
            break

    # Endereço: linhas de conteúdo após a linha do nome
    restantes = conteudo[idx_nome + 1:] if idx_nome is not None else []
    restantes = [l for l in restantes if not RE_CPF_CNPJ.fullmatch(l)]
    if restantes:
        dados.endereco = restantes[0]
    for linha_end in restantes:
        m_cep = RE_CEP.search(linha_end)
        if m_cep:
            dados.cep = m_cep.group(1) + m_cep.group(2)
            antes_cep = linha_end[: m_cep.start()]
            m_mun = RE_MUNICIPIO_UF.search(antes_cep)
            if m_mun:
                dados.municipio = m_mun.group(1).strip()
                dados.uf = m_mun.group(2)
                bairro = antes_cep[: m_mun.start()].strip(" -,")
                if bairro and bairro != dados.endereco:
                    dados.bairro = bairro or None
            break
