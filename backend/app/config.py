from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://camf:camf@db:5432/camf"
    # Onde os PDFs originais ficam guardados.
    # "disco": volume montado (Docker/VPS). "banco": dentro do PostgreSQL —
    # necessário em hospedagens gratuitas, que não têm disco persistente.
    armazenamento_modo: str = "disco"
    armazenamento_dir: str = "./armazenamento"
    # Build do React servido pela própria API em produção (vazio = só a API)
    frontend_dir: str = "./web"
    # Em produção com frontend embutido não há origem externa; a lista existe
    # para o arranjo com frontend hospedado à parte.
    origens_permitidas: list[str] = ["*"]

    empresa_nome: str = "CAMF Construtora LTDA"
    empresa_cnpj: str = "42.800.118/0001-44"
    banco_esperado: str = "756"  # Sicoob

    @field_validator("database_url")
    @classmethod
    def _normalizar_url(cls, valor: str) -> str:
        """Render/Railway/Heroku entregam 'postgres://', que o SQLAlchemy 2.0
        não reconhece — o driver precisa estar explícito."""
        if valor.startswith("postgres://"):
            return valor.replace("postgres://", "postgresql+psycopg2://", 1)
        if valor.startswith("postgresql://"):
            return valor.replace("postgresql://", "postgresql+psycopg2://", 1)
        return valor


settings = Settings()
