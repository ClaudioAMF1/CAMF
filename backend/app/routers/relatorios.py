from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Path, Query, Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import FiltrosBoleto
from ..models import Situacao
from ..services import dashboard as svc_dashboard
from ..services import modelos
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


# --- Modelos no layout dos relatórios impressos ------------------------------

TIPOS = {
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _somente_abertos(filtros: FiltrosBoleto) -> FiltrosBoleto:
    """Os dois modelos são de títulos em aberto, qualquer que seja a
    situação escolhida nos filtros da tela."""
    filtros.situacao = Situacao.aberto
    filtros.incluir_deletados = False
    return filtros


def _arquivo(conteudo: bytes, prefixo: str, formato: str) -> Response:
    nome = f"{prefixo}_{datetime.now():%Y%m%d_%H%M}.{formato}"
    return Response(
        content=conteudo,
        media_type=TIPOS[formato],
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


@router.get("/parcelas-em-aberto.{formato}")
def parcelas_em_aberto(
    formato: str = Path(pattern="^(pdf|xlsx)$"),
    filtros: FiltrosBoleto = Depends(),
    db: Session = Depends(get_db),
):
    """Agrupado por data de vencimento, com Total Cedente e Total por Data."""
    filtros = _somente_abertos(filtros)
    df = svc_dashboard.carregar_dataframe(db, filtros)
    periodo = modelos.periodo_dos_dados(df, filtros.vencimento_de, filtros.vencimento_ate)
    gerar = modelos.gerar_parcelas_pdf if formato == "pdf" else modelos.gerar_parcelas_xlsx
    return _arquivo(gerar(df, periodo), "parcelas_em_aberto", formato)


@router.get("/titulos.{formato}")
def titulos(
    formato: str = Path(pattern="^(pdf|xlsx)$"),
    taxa: Decimal | None = Query(default=None, ge=0, le=100, description="Tx. juros em %"),
    filtros: FiltrosBoleto = Depends(),
    db: Session = Depends(get_db),
):
    """Tipo, DOC, valor nominal/disponível, vencimento, taxa de juros e pagador."""
    filtros = _somente_abertos(filtros)
    df = svc_dashboard.carregar_dataframe(db, filtros)
    if formato == "pdf":
        periodo = modelos.periodo_dos_dados(df, filtros.vencimento_de, filtros.vencimento_ate)
        conteudo = modelos.gerar_titulos_pdf(df, taxa, periodo)
    else:
        conteudo = modelos.gerar_titulos_xlsx(df, taxa)
    return _arquivo(conteudo, "titulos_em_aberto", formato)
