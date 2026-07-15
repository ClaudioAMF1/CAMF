import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import boletos, dashboard, pagadores, relatorios, uploads

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="CAMF Contas a Receber",
    description="Gestão e análise de boletos bancários Sicoob (banco 756) — CAMF Construtora LTDA",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
