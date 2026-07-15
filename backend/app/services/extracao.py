"""Extração de dados de boletos Sicoob a partir do texto do PDF (pdfplumber).

A extração de texto é best-effort: qualquer campo que não bater com a
linha digitável vira divergência e manda o boleto para revisão manual.
"""

import io
import logging
import re
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
RE_NUMERO_COMPOSTO = re.compile(r"\b(\d+[-/]\d+)\b")

MARCADORES_BOLETO = ("SICOOB", "FICHA DE COMPENSAÇÃO", "FICHA DE COMPENSACAO")


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
    """Linhas do bloco 'Pagador' até o CPF/CNPJ ou fim do bloco."""
    m = re.search(r"Pagador\b[:\s]*", texto, re.IGNORECASE)
    if not m:
        return []
    trecho = texto[m.end(): m.end() + 400]
    corte = re.search(
        r"(Sacador|Avalista|Autentica|C[oó]digo de baixa|Beneficiário Final)",
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

    dados.vencimento = _parse_data(_apos_rotulo(texto, [r"Vencimento"], RE_DATA))
    dados.data_emissao = _parse_data(
        _apos_rotulo(texto, [r"Data d[eo] Documento", r"Data de Emiss[ãa]o"], RE_DATA)
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
        nome = re.sub(r"(CNPJ|CPF)[:\s]*$", "", nome.strip(), flags=re.IGNORECASE)
        dados.beneficiario_nome = nome.strip(" -:") .splitlines()[0].strip() or None

    # Bloco do pagador: nome + documento + endereço
    linhas = _bloco_pagador(texto)
    if linhas:
        primeira = linhas[0]
        m_doc = RE_CPF_CNPJ.search(primeira)
        if m_doc:
            dados.pagador_cpf_cnpj = m_doc.group(0)
            nome = primeira[: m_doc.start()]
        else:
            nome = primeira
            for linha_seg in linhas[1:]:
                m_doc = RE_CPF_CNPJ.search(linha_seg)
                if m_doc:
                    dados.pagador_cpf_cnpj = m_doc.group(0)
                    break
        dados.pagador_nome = re.sub(
            r"(CPF|CNPJ|CPF/CNPJ)[:\s]*$", "", nome.strip(), flags=re.IGNORECASE
        ).strip(" -:") or None

        restantes = [l for l in linhas[1:] if not RE_CPF_CNPJ.fullmatch(l)]
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

    return dados
