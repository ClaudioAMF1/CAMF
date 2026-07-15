from collections import defaultdict
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit, schemas
from ..database import get_db
from ..deps import get_autor
from ..models import Auditoria, Boleto, Pagador
from ..services import documentos

router = APIRouter(prefix="/api/pagadores", tags=["pagadores"])


def _nomes_alternativos(db: Session, pagador_ids: list[int]) -> dict[int, list[str]]:
    if not pagador_ids:
        return {}
    stmt = (
        select(Auditoria.entidade_id, Auditoria.valor_novo)
        .where(
            Auditoria.entidade == "pagador",
            Auditoria.entidade_id.in_(pagador_ids),
            Auditoria.acao == "divergencia_nome",
        )
        .order_by(Auditoria.id)
    )
    resultado: dict[int, list[str]] = defaultdict(list)
    for pagador_id, nome in db.execute(stmt):
        if nome and nome not in resultado[pagador_id]:
            resultado[pagador_id].append(nome)
    return resultado


def _estatisticas(db: Session, pagador_ids: list[int]) -> dict[int, tuple[int, Decimal]]:
    if not pagador_ids:
        return {}
    stmt = (
        select(Boleto.pagador_id, func.count(Boleto.id), func.coalesce(func.sum(Boleto.valor), 0))
        .where(Boleto.pagador_id.in_(pagador_ids))
        .group_by(Boleto.pagador_id)
    )
    return {pid: (qtd, Decimal(total)) for pid, qtd, total in db.execute(stmt)}


def _montar_out(db: Session, pagadores: list[Pagador]) -> list[schemas.PagadorOut]:
    ids = [p.id for p in pagadores]
    nomes = _nomes_alternativos(db, ids)
    stats = _estatisticas(db, ids)
    saida = []
    for p in pagadores:
        out = schemas.PagadorOut.model_validate(p)
        out.nomes_alternativos = nomes.get(p.id, [])
        out.qtd_boletos, out.total = stats.get(p.id, (0, Decimal("0")))
        saida.append(out)
    return saida


@router.get("", response_model=list[schemas.PagadorOut])
def listar(incluir_deletados: bool = False, db: Session = Depends(get_db)):
    stmt = select(Pagador).order_by(Pagador.nome)
    if incluir_deletados:
        stmt = stmt.execution_options(incluir_deletados=True)
    return _montar_out(db, db.execute(stmt).scalars().all())


@router.get("/sugestoes-merge", response_model=list[schemas.SugestaoMerge])
def sugestoes_merge(db: Session = Depends(get_db)):
    """Pagadores com mesmo nome normalizado e documentos diferentes.

    Apenas sugestão para a UI — o merge é sempre decisão manual do usuário.
    """
    duplicados = (
        select(Pagador.nome_normalizado)
        .group_by(Pagador.nome_normalizado)
        .having(func.count(Pagador.id) > 1)
    )
    stmt = (
        select(Pagador)
        .where(Pagador.nome_normalizado.in_(duplicados))
        .order_by(Pagador.nome_normalizado, Pagador.id)
    )
    grupos: dict[str, list[Pagador]] = defaultdict(list)
    for pagador in db.execute(stmt).scalars():
        grupos[pagador.nome_normalizado].append(pagador)
    return [
        schemas.SugestaoMerge(
            nome_normalizado=nome,
            pagadores=[schemas.PagadorBase.model_validate(p) for p in pagadores],
        )
        for nome, pagadores in grupos.items()
    ]


def _obter(db: Session, pagador_id: int, incluir_deletados: bool = False) -> Pagador:
    stmt = select(Pagador).where(Pagador.id == pagador_id)
    if incluir_deletados:
        stmt = stmt.execution_options(incluir_deletados=True)
    pagador = db.execute(stmt).scalar_one_or_none()
    if pagador is None:
        raise HTTPException(status_code=404, detail="Pagador não encontrado")
    return pagador


@router.get("/{pagador_id}", response_model=schemas.PagadorOut)
def detalhar(pagador_id: int, db: Session = Depends(get_db)):
    return _montar_out(db, [_obter(db, pagador_id, incluir_deletados=True)])[0]


def _executar_merge(db: Session, destino: Pagador, origem: Pagador, autor: str) -> None:
    """Migra os boletos da origem para o destino e soft-deleta a origem."""
    boletos = db.execute(
        select(Boleto)
        .where(Boleto.pagador_id == origem.id)
        .execution_options(incluir_deletados=True)
    ).scalars().all()
    for boleto in boletos:
        audit.registrar(
            db, "boleto", boleto.id, "editar",
            campo="pagador_id",
            valor_anterior=origem.id, valor_novo=destino.id,
            origem="manual", autor=autor,
        )
        boleto.pagador_id = destino.id
    origem.soft_delete()
    audit.registrar(
        db, "pagador", origem.id, "deletar",
        campo="merge", valor_novo=f"merge para pagador {destino.id}",
        origem="manual", autor=autor,
    )
    audit.registrar(
        db, "pagador", destino.id, "editar",
        campo="merge", valor_novo=f"recebeu boletos do pagador {origem.id}",
        origem="manual", autor=autor,
    )


@router.patch("/{pagador_id}", response_model=schemas.PagadorOut)
def editar(
    pagador_id: int,
    corpo: schemas.PagadorPatch,
    db: Session = Depends(get_db),
    autor: str = Depends(get_autor),
):
    pagador = _obter(db, pagador_id)
    alteracoes = corpo.model_dump(exclude_unset=True)

    if "cpf_cnpj" in alteracoes and alteracoes["cpf_cnpj"] is not None:
        normalizado = documentos.normalizar_cpf_cnpj(alteracoes["cpf_cnpj"])
        if normalizado is None:
            raise HTTPException(status_code=422, detail="CPF/CNPJ inválido")
        alteracoes["cpf_cnpj"] = normalizado
        existente = db.execute(
            select(Pagador).where(Pagador.cpf_cnpj == normalizado, Pagador.id != pagador.id)
        ).scalar_one_or_none()
        if existente is not None:
            # Correção de CPF de pagador provisório: merge com o pagador real
            _executar_merge(db, destino=existente, origem=pagador, autor=autor)
            db.commit()
            return _montar_out(db, [existente])[0]

    for campo, valor_novo in alteracoes.items():
        valor_anterior = getattr(pagador, campo)
        if valor_anterior == valor_novo:
            continue
        setattr(pagador, campo, valor_novo)
        if campo == "nome":
            pagador.nome_normalizado = documentos.normalizar_nome(valor_novo)
        audit.registrar(
            db, "pagador", pagador.id, "editar",
            campo=campo, valor_anterior=valor_anterior, valor_novo=valor_novo,
            origem="manual", autor=autor,
        )
    db.commit()
    return _montar_out(db, [pagador])[0]


@router.delete("/{pagador_id}", response_model=schemas.PagadorOut)
def deletar(pagador_id: int, db: Session = Depends(get_db), autor: str = Depends(get_autor)):
    """Soft delete de pagador sem boletos ativos (limpeza de provisórios órfãos)."""
    pagador = _obter(db, pagador_id)
    ativos = db.execute(
        select(func.count(Boleto.id)).where(Boleto.pagador_id == pagador.id)
    ).scalar_one()
    if ativos > 0:
        raise HTTPException(
            status_code=400,
            detail="Pagador tem boletos ativos; faça merge ou delete os boletos antes",
        )
    pagador.soft_delete()
    audit.registrar(db, "pagador", pagador.id, "deletar", origem="manual", autor=autor)
    db.commit()
    return _montar_out(db, [pagador])[0]


@router.post("/{pagador_id}/restaurar", response_model=schemas.PagadorOut)
def restaurar(pagador_id: int, db: Session = Depends(get_db), autor: str = Depends(get_autor)):
    pagador = _obter(db, pagador_id, incluir_deletados=True)
    if pagador.deletado_em is None:
        raise HTTPException(status_code=400, detail="Pagador não está deletado")
    pagador.restaurar()
    audit.registrar(db, "pagador", pagador.id, "restaurar", origem="manual", autor=autor)
    db.commit()
    return _montar_out(db, [pagador])[0]


@router.post("/{pagador_id}/merge", response_model=schemas.PagadorOut)
def merge(
    pagador_id: int,
    corpo: schemas.MergeIn,
    db: Session = Depends(get_db),
    autor: str = Depends(get_autor),
):
    destino = _obter(db, pagador_id)
    if corpo.pagador_origem_id == pagador_id:
        raise HTTPException(status_code=400, detail="Origem e destino são o mesmo pagador")
    origem = _obter(db, corpo.pagador_origem_id)
    _executar_merge(db, destino=destino, origem=origem, autor=autor)
    db.commit()
    return _montar_out(db, [destino])[0]
