"""Agregações do dashboard e dos relatórios, com pandas."""

from datetime import date
from decimal import Decimal

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..deps import FiltrosBoleto
from ..models import Boleto, Pagador


def carregar_dataframe(db: Session, filtros: FiltrosBoleto) -> pd.DataFrame:
    stmt = filtros.aplicar(
        select(Boleto)
        .join(Pagador, Boleto.pagador_id == Pagador.id)
        .options(joinedload(Boleto.pagador))
    )
    boletos = db.execute(stmt).scalars().all()
    linhas = [
        {
            "id": b.id,
            "pagador_id": b.pagador_id,
            "pagador_nome": b.pagador.nome if b.pagador else "",
            "pagador_cpf_cnpj": b.pagador.cpf_cnpj if b.pagador else None,
            "linha_digitavel": b.linha_digitavel,
            "nosso_numero": b.nosso_numero,
            "num_documento": b.num_documento,
            "data_emissao": b.data_emissao,
            "vencimento": b.vencimento,
            "valor": Decimal(b.valor),
            "situacao": b.situacao.value,
            "qualidade": b.qualidade.value,
            "vencido": b.vencido,
            "data_pagamento": b.data_pagamento,
            "valor_pago": Decimal(b.valor_pago) if b.valor_pago is not None else None,
            "divergencias": ", ".join(b.divergencias or []),
            "observacao": b.observacao,
        }
        for b in boletos
    ]
    return pd.DataFrame(linhas)


def _dec(valor) -> Decimal:
    return Decimal(str(valor)).quantize(Decimal("0.01"))


def montar_dashboard(df: pd.DataFrame) -> dict:
    if df.empty:
        return {
            "total_geral": Decimal("0"), "total_aberto": Decimal("0"),
            "total_pago": Decimal("0"), "total_vencido": Decimal("0"),
            "qtd_boletos": 0, "qtd_pagadores": 0,
            "valor_medio": Decimal("0"), "qtd_revisao_manual": 0,
            "por_pagador": [], "por_mes": [], "por_situacao": [],
        }

    por_pagador = (
        df.groupby(["pagador_nome", "valor"], as_index=False)
        .agg(qtd=("id", "count"))
        .assign(subtotal=lambda x: x["valor"] * x["qtd"])
        .sort_values(["pagador_nome", "valor"])
    )
    com_vencimento = df.dropna(subset=["vencimento"]).copy()
    if not com_vencimento.empty:
        com_vencimento["mes"] = com_vencimento["vencimento"].map(lambda d: f"{d:%Y-%m}")
        por_mes = (
            com_vencimento.groupby("mes", as_index=False)
            .agg(total=("valor", "sum"), qtd=("id", "count"))
            .sort_values("mes")
        )
    else:
        por_mes = pd.DataFrame(columns=["mes", "total", "qtd"])
    por_situacao = (
        df.groupby("situacao", as_index=False)
        .agg(qtd=("id", "count"), total=("valor", "sum"))
    )

    return {
        "total_geral": _dec(df["valor"].sum()),
        "total_aberto": _dec(df.loc[df["situacao"] == "aberto", "valor"].sum()),
        "total_pago": _dec(df.loc[df["situacao"] == "pago", "valor"].sum()),
        "total_vencido": _dec(df.loc[df["vencido"], "valor"].sum()),
        "qtd_boletos": int(len(df)),
        "qtd_pagadores": int(df["pagador_id"].nunique()),
        "valor_medio": _dec(df["valor"].mean()),
        "qtd_revisao_manual": int((df["qualidade"] == "revisao_manual").sum()),
        "por_pagador": [
            {
                "nome": r.pagador_nome,
                "qtd": int(r.qtd),
                "valor_unitario": _dec(r.valor),
                "subtotal": _dec(r.subtotal),
            }
            for r in por_pagador.itertuples()
        ],
        "por_mes": [
            {"mes": r.mes, "total": _dec(r.total), "qtd": int(r.qtd)}
            for r in por_mes.itertuples()
        ],
        "por_situacao": [
            {"situacao": r.situacao, "qtd": int(r.qtd), "total": _dec(r.total)}
            for r in por_situacao.itertuples()
        ],
    }


def alertas_vencimento(db: Session, dias: int) -> list[Boleto]:
    from datetime import timedelta

    from ..models import Situacao

    hoje = date.today()
    stmt = (
        select(Boleto)
        .join(Pagador, Boleto.pagador_id == Pagador.id)
        .options(joinedload(Boleto.pagador))
        .where(
            Boleto.situacao == Situacao.aberto,
            Boleto.vencimento >= hoje,
            Boleto.vencimento <= hoje + timedelta(days=dias),
        )
        .order_by(Boleto.vencimento)
    )
    return db.execute(stmt).scalars().all()
