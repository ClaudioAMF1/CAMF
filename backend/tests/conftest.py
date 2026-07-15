import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

# Configura o banco de testes ANTES de importar a aplicação
os.environ["DATABASE_URL"] = "sqlite:///./test_camf.db"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app
from app.services import extracao
from app.services.linha_digitavel import montar_linha


@pytest.fixture(autouse=True)
def banco_limpo():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def client():
    return TestClient(app)


def formatar_linha(linha47: str) -> str:
    """47 dígitos -> formato impresso no boleto."""
    return (
        f"{linha47[0:5]}.{linha47[5:10]} {linha47[10:15]}.{linha47[15:21]} "
        f"{linha47[21:26]}.{linha47[26:32]} {linha47[32]} {linha47[33:47]}"
    )


def valor_brl(valor: Decimal) -> str:
    return f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def texto_boleto(
    nome: str,
    cpf_cnpj: str | None,
    valor: Decimal,
    vencimento: date,
    sequencia: int = 1,
    num_documento: str = "2-01",
    nosso_numero: str = "1-1",
    valor_texto: Decimal | None = None,
    vencimento_texto: date | None = None,
) -> str:
    """Monta o texto de uma página de boleto Sicoob sintético."""
    linha = montar_linha(
        campo_livre=str(sequencia).rjust(25, "0"),
        valor=valor,
        vencimento=vencimento,
    )
    doc = f" CPF/CNPJ: {cpf_cnpj}" if cpf_cnpj else ""
    v_texto = valor_texto if valor_texto is not None else valor
    venc_texto = vencimento_texto if vencimento_texto is not None else vencimento
    return f"""SICOOB 756-0
Local de Pagamento PAGÁVEL PREFERENCIALMENTE NAS COOPERATIVAS DO SICOOB
Beneficiário CAMF CONSTRUTORA LTDA CNPJ: 42.800.118/0001-44
Data do Documento 01/06/2026 Nº do Documento {num_documento} Vencimento {venc_texto:%d/%m/%Y}
Carteira 1 Espécie Doc. DM Nosso Número {nosso_numero}
(=) Valor do Documento {valor_brl(v_texto)}
Pagador {nome}{doc}
RUA DAS FLORES, 123
CENTRO BELO HORIZONTE - MG 30100-000
Ficha de Compensação
{formatar_linha(linha)}
"""


def fake_pdf(paginas: list[str]) -> bytes:
    """PDF sintético: extrair_textos_paginas é monkeypatchado p/ decodificar isto."""
    return b"%PDF" + "\f".join(paginas).encode("utf-8")


@pytest.fixture(autouse=True)
def patch_extracao(monkeypatch):
    def _extrair(conteudo: bytes) -> list[str]:
        corpo = conteudo[len(b"%PDF"):].decode("utf-8")
        return corpo.split("\f") if corpo else []

    monkeypatch.setattr(extracao, "extrair_textos_paginas", _extrair)


def enviar(client, paginas_por_arquivo: dict[str, list[str]], forcar: bool = False):
    files = [
        ("arquivos", (nome, fake_pdf(paginas), "application/pdf"))
        for nome, paginas in paginas_por_arquivo.items()
    ]
    return client.post(f"/api/uploads?forcar={'true' if forcar else 'false'}", files=files)
