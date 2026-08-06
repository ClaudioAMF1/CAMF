import math
import unicodedata
from datetime import date, datetime
from decimal import Decimal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, joinedload

from .. import audit, schemas
from ..database import get_db
from ..deps import FiltrosBoleto, get_autor
from ..models import Auditoria, Boleto, Pagador, Qualidade, Situacao, Upload
from ..services import armazenamento, documentos, linha_digitavel

router = APIRouter(prefix="/api/boletos", tags=["boletos"])

COLUNAS_ORDENACAO = {
    "id": Boleto.id,
    "num_documento": Boleto.num_documento,
    "vencimento": Boleto.vencimento,
    "valor": Boleto.valor,
    "situacao": Boleto.situacao,
    "qualidade": Boleto.qualidade,
    "criado_em": Boleto.criado_em,
    "pagador": Pagador.nome,
}


def _cabecalho_arquivo(nome: str, inline: bool) -> dict[str, str]:
    """Content-Disposition com suporte a acentos (RFC 5987) e fallback ASCII."""
    disposicao = "inline" if inline else "attachment"
    ascii_seguro = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    ascii_seguro = ascii_seguro or "boleto.pdf"
    return {
        "Content-Disposition": (
            f'{disposicao}; filename="{ascii_seguro}"; '
            f"filename*=UTF-8''{quote(nome)}"
        )
    }


def nome_do_boleto(boleto: Boleto, pagador_nome: str | None = None) -> str:
    """"NOME DA PESSOA - 20-10-2026.pdf" — como o usuário arquiva os boletos."""
    nome = pagador_nome or (boleto.pagador.nome if boleto.pagador else None) or "Boleto"
    partes = [documentos.nome_arquivo_seguro(nome)]
    if boleto.vencimento:
        partes.append(f"{boleto.vencimento:%d-%m-%Y}")
    elif boleto.num_documento:
        partes.append(documentos.nome_arquivo_seguro(boleto.num_documento, 20))
    return " - ".join(partes) + ".pdf"


def _para_out(boleto: Boleto) -> schemas.BoletoOut:
    out = schemas.BoletoOut.model_validate(boleto)
    if boleto.pagador is not None:
        out.pagador_nome = boleto.pagador.nome
        out.pagador_cpf_cnpj = documentos.formatar_cpf_cnpj(boleto.pagador.cpf_cnpj)
    return out


def _obter(db: Session, boleto_id: int, incluir_deletados: bool = False) -> Boleto:
    stmt = (
        select(Boleto)
        .options(joinedload(Boleto.pagador))
        .where(Boleto.id == boleto_id)
    )
    if incluir_deletados:
        stmt = stmt.execution_options(incluir_deletados=True)
    boleto = db.execute(stmt).scalar_one_or_none()
    if boleto is None:
        raise HTTPException(status_code=404, detail="Boleto não encontrado")
    return boleto


@router.get("", response_model=schemas.PaginaBoletos)
def listar(
    filtros: FiltrosBoleto = Depends(),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=25, ge=1, le=200),
    sort: str = Query(default="-vencimento"),
    db: Session = Depends(get_db),
):
    stmt = filtros.aplicar(
        select(Boleto).join(Pagador, Boleto.pagador_id == Pagador.id)
        .options(joinedload(Boleto.pagador))
    )

    total = db.execute(
        stmt.with_only_columns(func.count(Boleto.id)).order_by(None)
    ).scalar_one()

    desc = sort.startswith("-")
    coluna = COLUNAS_ORDENACAO.get(sort.lstrip("-"), Boleto.vencimento)
    stmt = stmt.order_by(coluna.desc() if desc else coluna.asc(), Boleto.id)
    stmt = stmt.offset((page - 1) * size).limit(size)

    itens = db.execute(stmt).scalars().all()
    return schemas.PaginaBoletos(
        items=[_para_out(b) for b in itens],
        total=total,
        page=page,
        size=size,
        pages=max(1, math.ceil(total / size)),
    )


@router.get("/por-pagador", response_model=list[schemas.GrupoPagador])
def agrupados_por_pagador(
    filtros: FiltrosBoleto = Depends(), db: Session = Depends(get_db)
):
    """Uma linha por pessoa, com os totais dela — os boletos são carregados
    sob demanda ao expandir o nome (GET /boletos?pagador_id=...)."""
    hoje = date.today()
    eh_vencido = (Boleto.situacao == Situacao.aberto) & (Boleto.vencimento < hoje)

    def soma(condicao):
        return func.coalesce(func.sum(case((condicao, Boleto.valor), else_=0)), 0)

    def conta(condicao):
        return func.coalesce(func.sum(case((condicao, 1), else_=0)), 0)

    stmt = filtros.aplicar(
        select(
            Pagador.id,
            Pagador.nome,
            Pagador.cpf_cnpj,
            func.count(Boleto.id),
            func.coalesce(func.sum(Boleto.valor), 0),
            conta(Boleto.situacao == Situacao.aberto),
            soma(Boleto.situacao == Situacao.aberto),
            conta(Boleto.situacao == Situacao.pago),
            soma(Boleto.situacao == Situacao.pago),
            conta(eh_vencido),
            soma(eh_vencido),
            conta(Boleto.qualidade == Qualidade.revisao_manual),
            func.min(
                case((Boleto.situacao == Situacao.aberto, Boleto.vencimento))
            ),
        )
        .join(Pagador, Boleto.pagador_id == Pagador.id)
        .group_by(Pagador.id, Pagador.nome, Pagador.cpf_cnpj)
        .order_by(func.coalesce(func.sum(Boleto.valor), 0).desc())
    )

    # IDs por pagador, na mesma janela de filtros, para a seleção em massa
    ids_stmt = filtros.aplicar(
        select(Boleto.pagador_id, Boleto.id).join(Pagador, Boleto.pagador_id == Pagador.id)
    )
    ids_por_pagador: dict[int, list[int]] = {}
    for pagador_id, boleto_id in db.execute(ids_stmt):
        ids_por_pagador.setdefault(pagador_id, []).append(boleto_id)

    grupos = []
    for linha in db.execute(stmt):
        (pid, nome, cpf, qtd, total, q_ab, t_ab, q_pg, t_pg,
         q_vc, t_vc, q_rev, prox) = linha
        grupos.append(
            schemas.GrupoPagador(
                pagador_id=pid,
                nome=nome,
                cpf_cnpj=cpf,
                provisorio=cpf is None,
                qtd=qtd,
                total=Decimal(total),
                qtd_aberto=q_ab,
                total_aberto=Decimal(t_ab),
                qtd_pago=q_pg,
                total_pago=Decimal(t_pg),
                qtd_vencido=q_vc,
                total_vencido=Decimal(t_vc),
                qtd_revisao=q_rev,
                proximo_vencimento=prox,
                ids=ids_por_pagador.get(pid, []),
            )
        )
    return grupos


@router.get("/pdf-lote")
def pdf_em_lote(
    ids: str = Query(..., description="IDs separados por vírgula"),
    db: Session = Depends(get_db),
):
    """Junta os boletos pedidos num PDF só — para baixar ou imprimir de uma vez."""
    try:
        lista_ids = [int(x) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=422, detail="Lista de IDs inválida")
    if not lista_ids:
        raise HTTPException(status_code=400, detail="Nenhum boleto informado")

    stmt = (
        select(Boleto, Upload.hash_sha256)
        .join(Upload, Boleto.upload_id == Upload.id)
        .options(joinedload(Boleto.pagador))
        .where(Boleto.id.in_(lista_ids))
        .order_by(Boleto.vencimento, Boleto.id)
        .execution_options(incluir_deletados=True)
    )
    linhas = list(db.execute(stmt))
    if not linhas:
        raise HTTPException(status_code=404, detail="Boletos não encontrados")

    try:
        conteudo = armazenamento.juntar_paginas([(h, b.pagina) for b, h in linhas])
    except armazenamento.ArquivoIndisponivel:
        raise HTTPException(
            status_code=404,
            detail=(
                "Os PDFs originais destes boletos não estão guardados. Reenvie os "
                "arquivos em Enviar PDFs (com 'Reprocessar e atualizar')."
            ),
        )

    boletos = [b for b, _ in linhas]
    if len(boletos) == 1:
        nome = nome_do_boleto(boletos[0])
    else:
        # Um pagador só: usa o nome dele; vários: nomeia pelo período
        nomes = {b.pagador.nome for b in boletos if b.pagador}
        vencimentos = sorted(b.vencimento for b in boletos if b.vencimento)
        periodo = ""
        if vencimentos:
            periodo = (
                f" - {vencimentos[0]:%d-%m-%Y}"
                if vencimentos[0] == vencimentos[-1]
                else f" - {vencimentos[0]:%d-%m-%Y} a {vencimentos[-1]:%d-%m-%Y}"
            )
        base = (
            documentos.nome_arquivo_seguro(nomes.pop())
            if len(nomes) == 1
            else f"{len(boletos)} boletos"
        )
        nome = f"{base}{periodo}.pdf"

    return Response(
        content=conteudo,
        media_type="application/pdf",
        headers=_cabecalho_arquivo(nome, inline=False),
    )


@router.post("/pagar-lote", response_model=schemas.ResultadoLote)
def pagar_lote(
    corpo: schemas.PagarLoteIn,
    db: Session = Depends(get_db),
    autor: str = Depends(get_autor),
):
    """Baixa vários boletos de uma vez. Já pagos são ignorados, não viram erro."""
    if not corpo.ids:
        raise HTTPException(status_code=400, detail="Nenhum boleto informado")

    boletos = db.execute(select(Boleto).where(Boleto.id.in_(corpo.ids))).scalars().all()
    encontrados = {b.id for b in boletos}
    ignorados = [i for i in corpo.ids if i not in encontrados]
    pagos = 0

    for boleto in boletos:
        if boleto.situacao == Situacao.pago:
            ignorados.append(boleto.id)
            continue
        audit.registrar(
            db, "boleto", boleto.id, "marcar_pago",
            campo="situacao",
            valor_anterior=boleto.situacao.value,
            valor_novo=Situacao.pago.value,
            origem="manual", autor=autor,
        )
        boleto.situacao = Situacao.pago
        boleto.data_pagamento = corpo.data_pagamento
        boleto.valor_pago = corpo.valor_pago if corpo.valor_pago is not None else boleto.valor
        pagos += 1

    db.commit()
    return schemas.ResultadoLote(pagos=pagos, ignorados=sorted(ignorados))


@router.post("/deletar-lote", response_model=schemas.ResultadoAcaoLote)
def deletar_lote(
    corpo: schemas.IdsIn,
    db: Session = Depends(get_db),
    autor: str = Depends(get_autor),
):
    """Soft delete de vários boletos. Já deletados são ignorados, não viram erro."""
    if not corpo.ids:
        raise HTTPException(status_code=400, detail="Nenhum boleto informado")

    stmt = (
        select(Boleto)
        .where(Boleto.id.in_(corpo.ids))
        .execution_options(incluir_deletados=True)
    )
    boletos = db.execute(stmt).scalars().all()
    encontrados = {b.id for b in boletos}
    ignorados = [i for i in corpo.ids if i not in encontrados]
    afetados = 0

    for boleto in boletos:
        if boleto.deletado_em is not None:
            ignorados.append(boleto.id)
            continue
        boleto.soft_delete()
        audit.registrar(db, "boleto", boleto.id, "deletar", origem="manual", autor=autor)
        afetados += 1

    db.commit()
    return schemas.ResultadoAcaoLote(afetados=afetados, ignorados=sorted(ignorados))


@router.post("/restaurar-lote", response_model=schemas.ResultadoAcaoLote)
def restaurar_lote(
    corpo: schemas.IdsIn,
    db: Session = Depends(get_db),
    autor: str = Depends(get_autor),
):
    """Desfaz a exclusão de vários boletos de uma vez."""
    if not corpo.ids:
        raise HTTPException(status_code=400, detail="Nenhum boleto informado")

    stmt = (
        select(Boleto)
        .where(Boleto.id.in_(corpo.ids))
        .execution_options(incluir_deletados=True)
    )
    boletos = db.execute(stmt).scalars().all()
    encontrados = {b.id for b in boletos}
    ignorados = [i for i in corpo.ids if i not in encontrados]
    afetados = 0

    for boleto in boletos:
        if boleto.deletado_em is None:
            ignorados.append(boleto.id)
            continue
        boleto.restaurar()
        audit.registrar(db, "boleto", boleto.id, "restaurar", origem="manual", autor=autor)
        afetados += 1

    db.commit()
    return schemas.ResultadoAcaoLote(afetados=afetados, ignorados=sorted(ignorados))


@router.get("/{boleto_id}", response_model=schemas.BoletoOut)
def detalhar(boleto_id: int, db: Session = Depends(get_db)):
    return _para_out(_obter(db, boleto_id, incluir_deletados=True))


@router.get("/{boleto_id}/pdf")
def pdf_do_boleto(
    boleto_id: int,
    completo: bool = Query(default=False, description="Devolve o arquivo inteiro"),
    db: Session = Depends(get_db),
):
    """Abre o boleto original em PDF — só a página dele, por padrão."""
    boleto = _obter(db, boleto_id, incluir_deletados=True)
    upload = db.execute(
        select(Upload)
        .where(Upload.id == boleto.upload_id)
        .execution_options(incluir_deletados=True)
    ).scalar_one_or_none()
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload de origem não encontrado")

    try:
        if completo or boleto.pagina is None:
            conteudo = armazenamento.ler(upload.hash_sha256)
            nome = upload.nome_arquivo
        else:
            conteudo = armazenamento.extrair_pagina(upload.hash_sha256, boleto.pagina)
            nome = nome_do_boleto(boleto)
    except armazenamento.ArquivoIndisponivel:
        raise HTTPException(
            status_code=404,
            detail=(
                "PDF original não está guardado para este boleto. Reenvie o arquivo "
                "em Enviar PDFs (com 'Reprocessar e atualizar') para poder visualizá-lo."
            ),
        )
    except Exception:
        raise HTTPException(status_code=422, detail="Não foi possível ler o PDF original")

    return Response(
        content=conteudo,
        media_type="application/pdf",
        headers={**_cabecalho_arquivo(nome, inline=True), "Cache-Control": "private, max-age=300"},
    )


@router.get("/{boleto_id}/auditoria", response_model=list[schemas.AuditoriaOut])
def trilha_auditoria(boleto_id: int, db: Session = Depends(get_db)):
    _obter(db, boleto_id, incluir_deletados=True)
    stmt = (
        select(Auditoria)
        .where(Auditoria.entidade == "boleto", Auditoria.entidade_id == boleto_id)
        .order_by(Auditoria.id.desc())
    )
    return db.execute(stmt).scalars().all()


def _revalidar_qualidade(boleto: Boleto) -> None:
    """Revalida os campos contra a linha digitável e recalcula a qualidade."""
    analise = linha_digitavel.analisar(boleto.linha_digitavel)
    divergencias = [d for d in (boleto.divergencias or []) if d == "cpf_cnpj_ausente"]
    if analise is not None:
        divergencias += analise.erros
        if analise.valor is not None and boleto.valor != analise.valor:
            divergencias.append("valor_divergente")
        if analise.vencimento is not None and boleto.vencimento != analise.vencimento:
            divergencias.append("vencimento_divergente")
        if analise.valor is None:
            divergencias.append("valor_ausente_na_linha")
    boleto.divergencias = divergencias
    boleto.qualidade = Qualidade.revisao_manual if divergencias else Qualidade.ok


@router.patch("/{boleto_id}", response_model=schemas.BoletoOut)
def editar(
    boleto_id: int,
    corpo: schemas.BoletoPatch,
    db: Session = Depends(get_db),
    autor: str = Depends(get_autor),
):
    boleto = _obter(db, boleto_id)
    alteracoes = corpo.model_dump(exclude_unset=True)

    if "pagador_id" in alteracoes:
        novo_pagador = db.get(Pagador, alteracoes["pagador_id"])
        if novo_pagador is None or novo_pagador.deletado:
            raise HTTPException(status_code=400, detail="Pagador inválido")

    for campo, valor_novo in alteracoes.items():
        valor_anterior = getattr(boleto, campo)
        if valor_anterior == valor_novo:
            continue
        setattr(boleto, campo, valor_novo)
        audit.registrar(
            db, "boleto", boleto.id, "editar",
            campo=campo,
            valor_anterior=valor_anterior.value if hasattr(valor_anterior, "value") else valor_anterior,
            valor_novo=valor_novo.value if hasattr(valor_novo, "value") else valor_novo,
            origem="manual", autor=autor,
        )

    qualidade_anterior = boleto.qualidade
    _revalidar_qualidade(boleto)
    if boleto.qualidade != qualidade_anterior:
        audit.registrar(
            db, "boleto", boleto.id, "editar",
            campo="qualidade",
            valor_anterior=qualidade_anterior.value,
            valor_novo=boleto.qualidade.value,
            origem="manual", autor=autor,
        )
    db.commit()
    db.refresh(boleto)
    return _para_out(boleto)


@router.post("/{boleto_id}/pagar", response_model=schemas.BoletoOut)
def marcar_pago(
    boleto_id: int,
    corpo: schemas.PagarIn,
    db: Session = Depends(get_db),
    autor: str = Depends(get_autor),
):
    boleto = _obter(db, boleto_id)
    if boleto.situacao == Situacao.pago:
        raise HTTPException(status_code=400, detail="Boleto já está pago")
    audit.registrar(
        db, "boleto", boleto.id, "marcar_pago",
        campo="situacao",
        valor_anterior=boleto.situacao.value,
        valor_novo=Situacao.pago.value,
        origem="manual", autor=autor,
    )
    boleto.situacao = Situacao.pago
    boleto.data_pagamento = corpo.data_pagamento
    boleto.valor_pago = corpo.valor_pago
    db.commit()
    db.refresh(boleto)
    return _para_out(boleto)


@router.delete("/{boleto_id}", response_model=schemas.BoletoOut)
def deletar(boleto_id: int, db: Session = Depends(get_db), autor: str = Depends(get_autor)):
    boleto = _obter(db, boleto_id)
    boleto.soft_delete()
    audit.registrar(db, "boleto", boleto.id, "deletar", origem="manual", autor=autor)
    db.commit()
    return _para_out(boleto)


@router.post("/{boleto_id}/restaurar", response_model=schemas.BoletoOut)
def restaurar(boleto_id: int, db: Session = Depends(get_db), autor: str = Depends(get_autor)):
    boleto = _obter(db, boleto_id, incluir_deletados=True)
    if boleto.deletado_em is None:
        raise HTTPException(status_code=400, detail="Boleto não está deletado")
    boleto.restaurar()
    audit.registrar(db, "boleto", boleto.id, "restaurar", origem="manual", autor=autor)
    db.commit()
    return _para_out(boleto)
