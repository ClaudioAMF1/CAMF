"""Visualização do PDF original de cada boleto."""

import io
from datetime import date
from decimal import Decimal

import pytest
from pypdf import PdfReader, PdfWriter

from app.services import extracao

from .conftest import texto_boleto

CPF_A = "529.982.247-25"


def pdf_real(n_paginas: int) -> bytes:
    """PDF de verdade (pypdf) com N páginas — o binário guardado no disco."""
    escritor = PdfWriter()
    for _ in range(n_paginas):
        escritor.add_blank_page(width=595, height=842)  # A4
    buffer = io.BytesIO()
    escritor.write(buffer)
    return buffer.getvalue()


@pytest.fixture
def upload_real(client, monkeypatch, tmp_path):
    """Sobe um PDF real de 3 páginas, com a extração devolvendo 3 boletos."""
    from app.config import settings

    monkeypatch.setattr(settings, "armazenamento_dir", str(tmp_path / "pdfs"))

    textos = [
        texto_boleto("JOAO DA SILVA", CPF_A, Decimal(f"{100 + i}.00"),
                     date(2026, 8, 10 + i), sequencia=i + 1, num_documento=f"7-0{i + 1}")
        for i in range(3)
    ]
    monkeypatch.setattr(extracao, "extrair_textos_paginas", lambda _b: textos)

    conteudo = pdf_real(3)
    resp = client.post(
        "/api/uploads",
        files=[("arquivos", ("carteira.pdf", conteudo, "application/pdf"))],
    )
    assert resp.json()["arquivos"][0]["novos"] == 3
    return resp.json()["arquivos"][0]


def test_boleto_guarda_a_pagina_de_origem(client, upload_real):
    boletos = client.get("/api/boletos?sort=vencimento").json()["items"]
    assert [b["pagina"] for b in boletos] == [1, 2, 3]


def test_pdf_do_boleto_devolve_so_a_pagina_dele(client, upload_real):
    boletos = client.get("/api/boletos?sort=vencimento").json()["items"]
    segundo = boletos[1]

    resp = client.get(f"/api/boletos/{segundo['id']}/pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "inline" in resp.headers["content-disposition"]
    assert segundo["num_documento"] in resp.headers["content-disposition"]

    # é um PDF válido, de uma página só
    leitor = PdfReader(io.BytesIO(resp.content))
    assert len(leitor.pages) == 1


def test_pdf_completo_devolve_o_arquivo_inteiro(client, upload_real):
    boleto_id = client.get("/api/boletos").json()["items"][0]["id"]
    resp = client.get(f"/api/boletos/{boleto_id}/pdf?completo=true")
    assert len(PdfReader(io.BytesIO(resp.content)).pages) == 3

    resp_upload = client.get(f"/api/uploads/{upload_real['upload_id']}/pdf")
    assert len(PdfReader(io.BytesIO(resp_upload.content)).pages) == 3


def test_pdf_disponivel_mesmo_com_boleto_deletado(client, upload_real):
    boleto_id = client.get("/api/boletos").json()["items"][0]["id"]
    client.delete(f"/api/boletos/{boleto_id}")
    assert client.get(f"/api/boletos/{boleto_id}/pdf").status_code == 200


def test_sem_arquivo_guardado_explica_como_resolver(client, monkeypatch, tmp_path):
    """Uploads antigos (anteriores ao armazenamento) devem orientar, não quebrar."""
    from app.config import settings

    monkeypatch.setattr(settings, "armazenamento_dir", str(tmp_path / "vazio"))
    textos = [texto_boleto("MARIA SOUZA", CPF_A, Decimal("50.00"), date(2026, 9, 1), sequencia=9)]
    monkeypatch.setattr(extracao, "extrair_textos_paginas", lambda _b: textos)
    client.post("/api/uploads", files=[("arquivos", ("a.pdf", pdf_real(1), "application/pdf"))])

    boleto_id = client.get("/api/boletos").json()["items"][0]["id"]
    # simula o arquivo ausente em disco
    monkeypatch.setattr(settings, "armazenamento_dir", str(tmp_path / "outro-lugar"))

    resp = client.get(f"/api/boletos/{boleto_id}/pdf")
    assert resp.status_code == 404
    assert "Reenvie o arquivo" in resp.json()["detail"]


def test_reprocessar_atualiza_a_pagina(client, upload_real, monkeypatch, tmp_path):
    """Se o boleto mudar de página no arquivo, o vínculo acompanha."""
    from app.config import settings

    monkeypatch.setattr(settings, "armazenamento_dir", str(tmp_path / "pdfs"))
    boletos = client.get("/api/boletos?sort=vencimento").json()["items"]
    alvo = boletos[0]
    assert alvo["pagina"] == 1

    # mesmo boleto reenviado, agora na 2ª página de um arquivo novo
    textos = [
        texto_boleto("OUTRA PESSOA", "11.222.333/0001-81", Decimal("77.00"),
                     date(2026, 12, 1), sequencia=99),
        texto_boleto("JOAO DA SILVA", CPF_A, Decimal("100.00"),
                     date(2026, 8, 10), sequencia=1, num_documento="7-01"),
    ]
    monkeypatch.setattr(extracao, "extrair_textos_paginas", lambda _b: textos)
    client.post(
        "/api/uploads?forcar=true",
        files=[("arquivos", ("outra.pdf", pdf_real(2), "application/pdf"))],
    )

    atualizado = client.get(f"/api/boletos/{alvo['id']}").json()
    assert atualizado["pagina"] == 2
    assert len(PdfReader(io.BytesIO(client.get(f"/api/boletos/{alvo['id']}/pdf").content)).pages) == 1
