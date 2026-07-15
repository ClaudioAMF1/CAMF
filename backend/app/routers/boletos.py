import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from .. import audit, schemas
from ..database import get_db
from ..deps import FiltrosBoleto, get_autor
from ..models import Auditoria, Boleto, Pagador, Qualidade, Situacao
from ..services import linha_digitavel

router = APIRouter(prefix="/api/boletos", tags=["boletos"])

COLUNAS_ORDENACAO = {
    "id": Boleto.id,
    "vencimento": Boleto.vencimento,
    "valor": Boleto.valor,
    "situacao": Boleto.situacao,
    "qualidade": Boleto.qualidade,
    "criado_em": Boleto.criado_em,
    "pagador": Pagador.nome,
}


def _para_out(boleto: Boleto) -> schemas.BoletoOut:
    out = schemas.BoletoOut.model_validate(boleto)
    if boleto.pagador is not None:
        out.pagador_nome = boleto.pagador.nome
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


@router.get("/{boleto_id}", response_model=schemas.BoletoOut)
def detalhar(boleto_id: int, db: Session = Depends(get_db)):
    return _para_out(_obter(db, boleto_id, incluir_deletados=True))


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
