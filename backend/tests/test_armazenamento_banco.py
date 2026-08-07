"""PDFs guardados no banco — modo usado em hospedagem sem disco persistente."""

import io
from datetime import date
from decimal import Decimal

import pytest
from pypdf import PdfReader

from app.config import settings
from app.services import extracao

from .conftest import texto_boleto
from .test_pdf_boleto import pdf_real

CPF_A = "529.982.247-25"


@pytest.fixture
def modo_banco(monkeypatch, tmp_path):
    """Guarda no banco e aponta o disco para um diretório vazio: se algo
    escapar para o sistema de arquivos, o teste falha."""
    monkeypatch.setattr(settings, "armazenamento_modo", "banco")
    monkeypatch.setattr(settings, "armazenamento_dir", str(tmp_path / "nao-usar"))
    return tmp_path


@pytest.fixture
def upload_no_banco(client, modo_banco, monkeypatch):
    textos = [
        texto_boleto("JOAO DA SILVA", CPF_A, Decimal(f"{200 + i}.00"),
                     date(2026, 9, 10 + i), sequencia=i + 1, num_documento=f"5-0{i + 1}")
        for i in range(3)
    ]
    monkeypatch.setattr(extracao, "extrair_textos_paginas", lambda _b: textos)
    resp = client.post(
        "/api/uploads",
        files=[("arquivos", ("carteira.pdf", pdf_real(3), "application/pdf"))],
    )
    assert resp.json()["arquivos"][0]["novos"] == 3
    return resp.json()["arquivos"][0]


def test_pdf_do_boleto_vem_do_banco(client, upload_no_banco, modo_banco):
    boletos = client.get("/api/boletos?sort=vencimento").json()["items"]
    resp = client.get(f"/api/boletos/{boletos[1]['id']}/pdf")

    assert resp.status_code == 200
    assert len(PdfReader(io.BytesIO(resp.content)).pages) == 1
    # nada foi escrito em disco
    assert not (modo_banco / "nao-usar").exists()


def test_lote_e_arquivo_completo_tambem_funcionam(client, upload_no_banco):
    ids = ",".join(str(b["id"]) for b in client.get("/api/boletos").json()["items"][:2])
    lote = client.get(f"/api/boletos/pdf-lote?ids={ids}")
    assert len(PdfReader(io.BytesIO(lote.content)).pages) == 2

    completo = client.get(f"/api/uploads/{upload_no_banco['upload_id']}/pdf")
    assert len(PdfReader(io.BytesIO(completo.content)).pages) == 3


def test_mesmo_arquivo_nao_duplica_no_banco(client, modo_banco, monkeypatch):
    from sqlalchemy import func, select

    from app.database import SessionLocal
    from app.models import ArquivoPdf

    textos = [texto_boleto("MARIA SOUZA", CPF_A, Decimal("80.00"), date(2026, 10, 1), sequencia=8)]
    monkeypatch.setattr(extracao, "extrair_textos_paginas", lambda _b: textos)
    conteudo = pdf_real(1)

    client.post("/api/uploads", files=[("arquivos", ("a.pdf", conteudo, "application/pdf"))])
    client.post(
        "/api/uploads?forcar=true",
        files=[("arquivos", ("a.pdf", conteudo, "application/pdf"))],
    )

    with SessionLocal() as db:
        assert db.execute(select(func.count(ArquivoPdf.hash_sha256))).scalar_one() == 1


def test_sem_o_arquivo_no_banco_orienta_o_reenvio(client, modo_banco, monkeypatch):
    from app.database import SessionLocal
    from app.models import ArquivoPdf

    textos = [texto_boleto("JOAO DA SILVA", CPF_A, Decimal("90.00"), date(2026, 11, 1), sequencia=9)]
    monkeypatch.setattr(extracao, "extrair_textos_paginas", lambda _b: textos)
    client.post("/api/uploads", files=[("arquivos", ("a.pdf", pdf_real(1), "application/pdf"))])

    boleto_id = client.get("/api/boletos").json()["items"][0]["id"]
    with SessionLocal() as db:  # simula base migrada de outra hospedagem
        db.query(ArquivoPdf).delete()
        db.commit()

    resp = client.get(f"/api/boletos/{boleto_id}/pdf")
    assert resp.status_code == 404
    assert "Reenvie o arquivo" in resp.json()["detail"]
