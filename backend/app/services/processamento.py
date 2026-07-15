"""Processamento de uploads: extração, validação cruzada, identidade do
pagador, deduplicação e auditoria."""

import hashlib
import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..models import Boleto, Pagador, Qualidade, Situacao, Upload
from . import documentos, extracao, linha_digitavel

logger = logging.getLogger("camf.processamento")


class ArquivoJaProcessado(Exception):
    def __init__(self, upload: Upload):
        self.upload = upload
        super().__init__(f"Arquivo já processado no upload {upload.id}")


@dataclass
class ResultadoArquivo:
    nome: str
    upload_id: int | None = None
    novos: int = 0
    duplicados: int = 0
    ignoradas: list[int] = field(default_factory=list)
    revisao_manual: int = 0
    erro: str | None = None


def _buscar_upload_por_hash(db: Session, hash_sha256: str) -> Upload | None:
    stmt = (
        select(Upload)
        .where(Upload.hash_sha256 == hash_sha256)
        .order_by(Upload.id.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def _buscar_boleto_por_linha(db: Session, linha: str) -> Boleto | None:
    # Inclui deletados: a linha digitável é UNIQUE mesmo entre soft-deletados.
    stmt = (
        select(Boleto)
        .where(Boleto.linha_digitavel == linha)
        .execution_options(incluir_deletados=True)
    )
    return db.execute(stmt).scalar_one_or_none()


def resolver_pagador(
    db: Session, dados: extracao.DadosPagina, autor: str
) -> tuple[Pagador, list[str]]:
    """Resolve a identidade do pagador pela chave cpf_cnpj normalizado.

    Retorna o pagador e a lista de divergências geradas (ex: cpf_cnpj_ausente).
    Nunca faz match automático por similaridade de nome.
    """
    divergencias: list[str] = []
    nome = dados.pagador_nome or "PAGADOR NAO IDENTIFICADO"
    nome_norm = documentos.normalizar_nome(nome)
    cpf_cnpj = documentos.normalizar_cpf_cnpj(dados.pagador_cpf_cnpj)

    if cpf_cnpj is None:
        # CPF/CNPJ ausente ou inválido: pagador provisório por nome_normalizado
        divergencias.append("cpf_cnpj_ausente")
        stmt = select(Pagador).where(
            Pagador.cpf_cnpj.is_(None), Pagador.nome_normalizado == nome_norm
        )
        pagador = db.execute(stmt).scalars().first()
        if pagador is None:
            pagador = _criar_pagador(db, None, nome, nome_norm, dados, autor)
        return pagador, divergencias

    stmt = select(Pagador).where(Pagador.cpf_cnpj == cpf_cnpj)
    pagador = db.execute(stmt).scalar_one_or_none()
    if pagador is None:
        pagador = _criar_pagador(db, cpf_cnpj, nome, nome_norm, dados, autor)
        return pagador, divergencias

    # Pagador já existe: nome do PDF diferente não sobrescreve o cadastro,
    # apenas registra a variação na auditoria (exposta como nomes_alternativos).
    if nome_norm and nome_norm != pagador.nome_normalizado:
        ja_registrado = db.execute(
            select(audit.Auditoria.id).where(
                audit.Auditoria.entidade == "pagador",
                audit.Auditoria.entidade_id == pagador.id,
                audit.Auditoria.acao == "divergencia_nome",
                audit.Auditoria.valor_novo == nome,
            )
        ).first()
        if not ja_registrado:
            audit.registrar(
                db,
                "pagador",
                pagador.id,
                "divergencia_nome",
                campo="nome",
                valor_anterior=pagador.nome,
                valor_novo=nome,
                origem="extracao",
                autor=autor,
            )
    return pagador, divergencias


def _criar_pagador(
    db: Session,
    cpf_cnpj: str | None,
    nome: str,
    nome_norm: str,
    dados: extracao.DadosPagina,
    autor: str,
) -> Pagador:
    pagador = Pagador(
        cpf_cnpj=cpf_cnpj,
        nome=nome,
        nome_normalizado=nome_norm,
        endereco=dados.endereco,
        bairro=dados.bairro,
        municipio=dados.municipio,
        uf=dados.uf,
        cep=documentos.somente_digitos(dados.cep) or None,
    )
    db.add(pagador)
    db.flush()
    audit.registrar(
        db, "pagador", pagador.id, "criar", origem="extracao", autor=autor
    )
    return pagador


def validar_cruzado(
    resultado: linha_digitavel.ResultadoLinha, dados: extracao.DadosPagina
) -> tuple[list[str], list[str]]:
    """Compara texto extraído com a linha digitável (fonte da verdade).

    Retorna (divergencias, observacoes).
    """
    divergencias = list(resultado.erros)
    observacoes: list[str] = []

    if dados.valor is not None and resultado.valor is not None and dados.valor != resultado.valor:
        divergencias.append("valor_divergente")
        observacoes.append(f"Valor no texto do PDF: {dados.valor}")
    if (
        dados.vencimento is not None
        and resultado.vencimento is not None
        and dados.vencimento != resultado.vencimento
    ):
        divergencias.append("vencimento_divergente")
        observacoes.append(f"Vencimento no texto do PDF: {dados.vencimento:%d/%m/%Y}")
    if resultado.valor is None:
        divergencias.append("valor_ausente_na_linha")
    return divergencias, observacoes


def _preencher_extracao(
    boleto: Boleto,
    upload_id: int,
    pagador_id: int,
    analise: linha_digitavel.ResultadoLinha,
    dados: extracao.DadosPagina,
    divergencias: list[str],
    observacoes: list[str],
) -> None:
    """Aplica ao boleto os campos vindos da extração (linha digitável autoritativa)."""
    boleto.upload_id = upload_id
    boleto.pagador_id = pagador_id
    boleto.codigo_barras = analise.codigo_barras
    boleto.nosso_numero = dados.nosso_numero
    boleto.num_documento = dados.num_documento
    boleto.especie = dados.especie
    boleto.carteira = dados.carteira
    boleto.data_emissao = dados.data_emissao
    boleto.vencimento = analise.vencimento or dados.vencimento
    boleto.valor = analise.valor if analise.valor is not None else (dados.valor or 0)
    boleto.beneficiario_nome = dados.beneficiario_nome
    boleto.beneficiario_cnpj = (
        documentos.normalizar_cpf_cnpj(dados.beneficiario_cnpj)
        or documentos.somente_digitos(dados.beneficiario_cnpj)
        or None
    )
    boleto.qualidade = Qualidade.revisao_manual if divergencias else Qualidade.ok
    boleto.divergencias = divergencias
    boleto.observacao = "\n".join(observacoes) or None


def processar_arquivo(
    db: Session,
    nome_arquivo: str,
    conteudo: bytes,
    forcar: bool = False,
    autor: str = "sistema",
) -> ResultadoArquivo:
    """Processa um PDF. Levanta ArquivoJaProcessado se hash já existe e forcar=False."""
    hash_sha256 = hashlib.sha256(conteudo).hexdigest()
    anterior = _buscar_upload_por_hash(db, hash_sha256)
    if anterior is not None and not forcar:
        raise ArquivoJaProcessado(anterior)

    textos = extracao.extrair_textos_paginas(conteudo)

    upload = Upload(
        nome_arquivo=nome_arquivo,
        hash_sha256=hash_sha256,
        qtd_paginas=len(textos),
        reprocessado_de_id=anterior.id if anterior else None,
    )
    db.add(upload)
    db.flush()
    audit.registrar(db, "upload", upload.id, "criar", origem="extracao", autor=autor)

    resultado = ResultadoArquivo(nome=nome_arquivo, upload_id=upload.id)

    for num_pagina, texto in enumerate(textos, start=1):
        dados = extracao.extrair_dados_pagina(texto)
        if dados is None:
            # Sem linha digitável não há chave única: página ignorada.
            resultado.ignoradas.append(num_pagina)
            upload.qtd_ignoradas += 1
            if extracao.parece_boleto(texto):
                logger.warning(
                    "Página %s de %s parece boleto Sicoob mas a linha digitável "
                    "não foi reconhecida — possível falha de parsing",
                    num_pagina,
                    nome_arquivo,
                )
            continue

        analise = linha_digitavel.analisar(dados.linha_digitavel_bruta)
        if analise is None:  # não deveria ocorrer, mas protege o lote
            resultado.ignoradas.append(num_pagina)
            upload.qtd_ignoradas += 1
            continue

        existente = _buscar_boleto_por_linha(db, analise.linha_digitavel)
        if existente is not None and existente.deletado_em is None:
            resultado.duplicados += 1
            upload.qtd_duplicados += 1
            continue

        pagador, divergencias_pagador = resolver_pagador(db, dados, autor)
        divergencias, observacoes = validar_cruzado(analise, dados)
        divergencias = divergencias_pagador + divergencias

        if existente is not None:
            # Boleto soft-deletado reaparecendo no PDF: reaproveita o registro
            # (a linha digitável é UNIQUE), atualizando com a extração nova.
            # É o caminho de reparo: deletar o upload e reenviar com forcar=true
            # depois de uma correção do parser.
            boleto = existente
            _preencher_extracao(boleto, upload.id, pagador.id, analise, dados,
                                divergencias, observacoes)
            boleto.restaurar()
            audit.registrar(
                db, "boleto", boleto.id, "restaurar",
                campo="reextracao", origem="extracao", autor=autor,
            )
        else:
            boleto = Boleto(linha_digitavel=analise.linha_digitavel, situacao=Situacao.aberto)
            _preencher_extracao(boleto, upload.id, pagador.id, analise, dados,
                                divergencias, observacoes)
            db.add(boleto)
            db.flush()
            audit.registrar(db, "boleto", boleto.id, "criar", origem="extracao", autor=autor)

        resultado.novos += 1
        upload.qtd_boletos_novos += 1
        if divergencias:
            resultado.revisao_manual += 1
            upload.qtd_revisao += 1

    db.flush()
    return resultado
