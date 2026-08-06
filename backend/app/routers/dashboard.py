from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db
from ..deps import FiltrosBoleto
from ..services import dashboard as svc
from ..services import documentos

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=schemas.DashboardOut)
def dashboard(filtros: FiltrosBoleto = Depends(), db: Session = Depends(get_db)):
    df = svc.carregar_dataframe(db, filtros)
    return svc.montar_dashboard(df)


@router.get("/alertas", response_model=list[schemas.BoletoOut])
def alertas(
    dias: int = Query(default=30, ge=1, le=365),
    de: date | None = Query(default=None),
    ate: date | None = Query(default=None),
    incluir_vencidos: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """Boletos em aberto a vencer: próximos N dias ou um intervalo (ex.: o mês)."""
    boletos = svc.alertas_vencimento(db, dias, de=de, ate=ate, incluir_vencidos=incluir_vencidos)
    saida = []
    for b in boletos:
        out = schemas.BoletoOut.model_validate(b)
        if b.pagador:
            out.pagador_nome = b.pagador.nome
            out.pagador_cpf_cnpj = documentos.formatar_cpf_cnpj(b.pagador.cpf_cnpj)
        saida.append(out)
    return saida
