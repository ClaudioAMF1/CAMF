"""API e interface servidas por um único serviço (imagem de produção)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import montar_frontend


def _build_falso(tmp_path):
    """Reproduz o layout de um build do Vite."""
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>CAMF</title>")
    (tmp_path / "assets" / "index-abc.js").write_text("console.log(1)")
    (tmp_path / "favicon.ico").write_text("x")
    return tmp_path


def test_sem_build_a_api_sobe_normalmente(tmp_path):
    app = FastAPI()
    assert montar_frontend(app, tmp_path / "inexistente") is False


def test_rotas_do_react_caem_no_index(tmp_path):
    app = FastAPI()

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    assert montar_frontend(app, _build_falso(tmp_path)) is True
    client = TestClient(app)

    # a API continua respondendo JSON
    assert client.get("/api/health").json() == {"status": "ok"}

    # rotas do React Router (inclusive ao recarregar a página) devolvem o index
    for rota in ["/", "/boletos", "/vencimentos", "/pagadores"]:
        resp = client.get(rota)
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "CAMF" in resp.text

    # arquivos estáticos são entregues como arquivo
    assert client.get("/assets/index-abc.js").status_code == 200
    assert client.get("/favicon.ico").text == "x"


def test_nao_serve_arquivo_fora_do_diretorio(tmp_path):
    """Uma rota com ../ não pode escapar do diretório do frontend."""
    segredo = tmp_path / "segredo.txt"
    segredo.write_text("nao deve vazar")
    (tmp_path / "web").mkdir()
    build = _build_falso(tmp_path / "web")

    app = FastAPI()
    montar_frontend(app, build)
    resp = TestClient(app).get("/../segredo.txt")

    assert "nao deve vazar" not in resp.text
    assert "CAMF" in resp.text  # cai no index, como qualquer rota desconhecida
