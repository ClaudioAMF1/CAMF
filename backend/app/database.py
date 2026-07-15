from datetime import datetime, timezone

from sqlalchemy import DateTime, create_engine, event
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    sessionmaker,
    with_loader_criteria,
)

from .config import settings


class Base(DeclarativeBase):
    pass


class SoftDeleteMixin:
    """Soft delete: deletado_em preenchido = registro inativo.

    Um listener em Session.do_orm_execute injeta automaticamente o filtro
    `deletado_em IS NULL` em todo SELECT, a menos que a query rode com
    `.execution_options(incluir_deletados=True)`.
    """

    deletado_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    @property
    def deletado(self) -> bool:
        return self.deletado_em is not None

    def soft_delete(self, quando: datetime | None = None) -> None:
        self.deletado_em = quando or datetime.now(timezone.utc)

    def restaurar(self) -> None:
        self.deletado_em = None


_engine_kwargs: dict = {}
if settings.database_url.startswith("sqlite"):
    # Usado apenas nos testes; produção é PostgreSQL
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(
    settings.database_url, pool_pre_ping=True, future=True, **_engine_kwargs
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@event.listens_for(Session, "do_orm_execute")
def _filtrar_soft_delete(execute_state):
    if (
        execute_state.is_select
        and not execute_state.is_column_load
        and not execute_state.is_relationship_load
        and not execute_state.execution_options.get("incluir_deletados", False)
    ):
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                SoftDeleteMixin,
                lambda cls: cls.deletado_em.is_(None),
                include_aliases=True,
            )
        )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
