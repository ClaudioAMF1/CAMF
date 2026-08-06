import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .routers import boletos, dashboard, pagadores, relatorios, uploads

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("camf")

app = FastAPI(
    title="CAMF Contas a Receber",
    description="Gestão e análise de boletos bancários Sicoob (banco 756) — CAMF Construtora LTDA",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origens_permitidas,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(uploads.router)
app.include_router(boletos.router)
app.include_router(pagadores.router)
app.include_router(dashboard.router)
app.include_router(relatorios.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# --- Frontend embutido -------------------------------------------------------

def montar_frontend(aplicacao: FastAPI, diretorio: Path) -> bool:
    """Serve o build do React pela própria API (um serviço só, sem CORS).

    Em desenvolvimento o diretório não existe e o Vite segue servindo o
    frontend na porta dele. Devolve True quando o frontend foi montado.
    """
    if not (diretorio / "index.html").is_file():
        return False

    raiz = diretorio.resolve()
    if (diretorio / "assets").is_dir():
        aplicacao.mount("/assets", StaticFiles(directory=diretorio / "assets"), name="assets")

    @aplicacao.get("/{caminho:path}", include_in_schema=False)
    def servir_spa(caminho: str):
        """Entrega o arquivo pedido ou o index.html (rotas do React Router)."""
        arquivo = (raiz / caminho).resolve()
        # `raiz in parents` impede que ../ escape do diretório do frontend
        if caminho and raiz in arquivo.parents and arquivo.is_file():
            return FileResponse(arquivo)
        return FileResponse(raiz / "index.html")

    logger.info("Frontend servido de %s", raiz)
    return True


montar_frontend(app, Path(settings.frontend_dir))
