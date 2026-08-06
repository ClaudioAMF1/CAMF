from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import FiltrosBoleto
from ..services import dashboard as svc_dashboard
from ..services import relatorios as svc

router = APIRouter(prefix="/api/relatorios", tags=["relatorios"])


def _nome(extensao: str) -> str:
    return f"contas_a_receber_{datetime.now():%Y%m%d_%H%M}.{extensao}"


@router.get("/pdf")
def relatorio_pdf(filtros: FiltrosBoleto = Depends(), db: Session = Depends(get_db)):
    df = svc_dashboard.carregar_dataframe(db, filtros)
    resumo = svc_dashboard.montar_dashboard(df)
    conteudo = svc.gerar_pdf(df, resumo, filtros.descricao_periodo())
    return Response(
        content=conteudo,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{_nome("pdf")}"'},
    )


@router.get("/xlsx")
def relatorio_xlsx(filtros: FiltrosBoleto = Depends(), db: Session = Depends(get_db)):
    df = svc_dashboard.carregar_dataframe(db, filtros)
    resumo = svc_dashboard.montar_dashboard(df)
    conteudo = svc.gerar_xlsx(df, resumo)
    return Response(
        content=conteudo,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{_nome("xlsx")}"'},
    )


@router.get("/csv")
def relatorio_csv(
    filtros: FiltrosBoleto = Depends(),
    aba: str = Query(default="boletos", pattern="^(boletos|pagadores)$"),
    db: Session = Depends(get_db),
):
    """CSV dos boletos (padrão) ou dos pagadores com dados cadastrais."""
    df = svc_dashboard.carregar_dataframe(db, filtros)
    conteudo = svc.gerar_csv_pagadores(df) if aba == "pagadores" else svc.gerar_csv(df)
    nome = _nome("csv") if aba == "boletos" else f"pagadores_{datetime.now():%Y%m%d_%H%M}.csv"
    return Response(
        content=conteudo,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )
