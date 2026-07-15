from sqlalchemy.orm import Session

from .models import Auditoria


def registrar(
    db: Session,
    entidade: str,
    entidade_id: int,
    acao: str,
    campo: str | None = None,
    valor_anterior=None,
    valor_novo=None,
    origem: str = "manual",
    autor: str = "sistema",
) -> Auditoria:
    """Insere um registro na trilha de auditoria (append-only)."""
    reg = Auditoria(
        entidade=entidade,
        entidade_id=entidade_id,
        acao=acao,
        campo=campo,
        valor_anterior=None if valor_anterior is None else str(valor_anterior),
        valor_novo=None if valor_novo is None else str(valor_novo),
        origem=origem,
        autor=autor,
    )
    db.add(reg)
    return reg
