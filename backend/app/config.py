from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://camf:camf@db:5432/camf"
    empresa_nome: str = "CAMF Construtora LTDA"
    empresa_cnpj: str = "42.800.118/0001-44"
    banco_esperado: str = "756"  # Sicoob


settings = Settings()
