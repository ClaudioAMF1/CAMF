from datetime import date
from decimal import Decimal

from fastapi import Header, Query
from sqlalchemy import Select

from .models import Boleto, Qualidade, Situacao


def get_autor(x_autor: str = Header(default="sistema")) -> str:
    """Autor das mudanças, vindo do header X-Autor (pronto p/ evoluir p/ auth)."""
    return x_autor.strip() or "sistema"


class FiltrosBoleto:
    """Filtros compartilhados por /boletos, /dashboard e /relatorios."""

    def __init__(
        self,
        pagador_id: int | None = Query(default=None),
        situacao: Situacao | None = Query(default=None),
        qualidade: Qualidade | None = Query(default=None),
        vencido: bool | None = Query(default=None),
        vencimento_de: date | None = Query(default=None),
        vencimento_ate: date | None = Query(default=None),
        valor_min: Decimal | None = Query(default=None),
        valor_max: Decimal | None = Query(default=None),
        incluir_deletados: bool = Query(default=False),
    ):
        self.pagador_id = pagador_id
        self.situacao = situacao
        self.qualidade = qualidade
        self.vencido = vencido
        self.vencimento_de = vencimento_de
        self.vencimento_ate = vencimento_ate
        self.valor_min = valor_min
        self.valor_max = valor_max
        self.incluir_deletados = incluir_deletados

    def aplicar(self, stmt: Select) -> Select:
        if self.pagador_id is not None:
            stmt = stmt.where(Boleto.pagador_id == self.pagador_id)
        if self.situacao is not None:
            stmt = stmt.where(Boleto.situacao == self.situacao)
        if self.qualidade is not None:
            stmt = stmt.where(Boleto.qualidade == self.qualidade)
        if self.vencido is not None:
            # 'vencido' é derivado: aberto + vencimento no passado
            cond = (Boleto.situacao == Situacao.aberto) & (Boleto.vencimento < date.today())
            stmt = stmt.where(cond if self.vencido else ~cond)
        if self.vencimento_de is not None:
            stmt = stmt.where(Boleto.vencimento >= self.vencimento_de)
        if self.vencimento_ate is not None:
            stmt = stmt.where(Boleto.vencimento <= self.vencimento_ate)
        if self.valor_min is not None:
            stmt = stmt.where(Boleto.valor >= self.valor_min)
        if self.valor_max is not None:
            stmt = stmt.where(Boleto.valor <= self.valor_max)
        if self.incluir_deletados:
            stmt = stmt.execution_options(incluir_deletados=True)
        return stmt

    def descricao_periodo(self) -> str:
        if self.vencimento_de and self.vencimento_ate:
            return f"{self.vencimento_de:%d/%m/%Y} a {self.vencimento_ate:%d/%m/%Y}"
        if self.vencimento_de:
            return f"a partir de {self.vencimento_de:%d/%m/%Y}"
        if self.vencimento_ate:
            return f"até {self.vencimento_ate:%d/%m/%Y}"
        return "todo o período"
