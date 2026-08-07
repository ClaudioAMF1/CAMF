"""Guarda os PDFs originais para que cada boleto possa ser reaberto.

Dois modos, escolhidos por ARMAZENAMENTO_MODO:

- "disco" (padrão): arquivos num volume, nomeados pelo hash SHA-256.
- "banco": bytes dentro do PostgreSQL. É o que permite rodar em hospedagem
  gratuita, onde o sistema de arquivos é apagado a cada deploy.

Em ambos, o hash é a chave: reenviar o mesmo PDF não duplica nada.
"""

import io
import logging
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from sqlalchemy.orm import Session

from ..config import settings
from ..models import ArquivoPdf

logger = logging.getLogger("camf.armazenamento")


class ArquivoIndisponivel(Exception):
    """PDF original não está guardado (ex.: upload anterior a este recurso)."""


def _no_banco() -> bool:
    return settings.armazenamento_modo.lower() == "banco"


def _raiz() -> Path:
    caminho = Path(settings.armazenamento_dir)
    caminho.mkdir(parents=True, exist_ok=True)
    return caminho


def caminho_do_hash(hash_sha256: str) -> Path:
    return _raiz() / f"{hash_sha256}.pdf"


def guardar(hash_sha256: str, conteudo: bytes, db: Session | None = None) -> None:
    if _no_banco():
        if db is None:
            logger.warning("Modo banco sem sessão: PDF %s não guardado", hash_sha256)
            return
        if db.get(ArquivoPdf, hash_sha256) is None:
            db.add(ArquivoPdf(
                hash_sha256=hash_sha256, conteudo=conteudo, tamanho=len(conteudo)
            ))
            db.flush()
        return

    destino = caminho_do_hash(hash_sha256)
    if destino.exists():
        return  # mesmo conteúdo, mesmo arquivo
    try:
        destino.write_bytes(conteudo)
    except OSError:
        # Falha ao gravar não pode derrubar a importação dos boletos
        logger.warning("Não foi possível guardar o PDF %s", hash_sha256, exc_info=True)


def ler(hash_sha256: str, db: Session | None = None) -> bytes:
    if _no_banco():
        registro = db.get(ArquivoPdf, hash_sha256) if db is not None else None
        if registro is None:
            raise ArquivoIndisponivel(hash_sha256)
        return registro.conteudo

    caminho = caminho_do_hash(hash_sha256)
    if not caminho.exists():
        raise ArquivoIndisponivel(hash_sha256)
    return caminho.read_bytes()


def juntar_paginas(
    itens: list[tuple[str, int | None]], db: Session | None = None
) -> bytes:
    """Junta várias páginas (hash, página) num PDF só, para baixar em lote.

    Itens cujo arquivo não está guardado são pulados — o que existe é entregue.
    """
    escritor = PdfWriter()
    for hash_sha256, numero_pagina in itens:
        try:
            leitor = PdfReader(io.BytesIO(ler(hash_sha256, db)))
        except Exception:  # arquivo ausente ou PDF ilegível: pula esse item
            logger.warning("PDF indisponível ao montar o lote: %s", hash_sha256)
            continue
        if numero_pagina is None:
            for pagina in leitor.pages:
                escritor.add_page(pagina)
        elif 1 <= numero_pagina <= len(leitor.pages):
            escritor.add_page(leitor.pages[numero_pagina - 1])

    if not escritor.pages:
        raise ArquivoIndisponivel("nenhum PDF disponível para os boletos pedidos")

    buffer = io.BytesIO()
    escritor.write(buffer)
    return buffer.getvalue()


def extrair_pagina(
    hash_sha256: str, numero_pagina: int, db: Session | None = None
) -> bytes:
    """Devolve um PDF de uma página só — a do boleto pedido (1-indexado)."""
    leitor = PdfReader(io.BytesIO(ler(hash_sha256, db)))
    if not 1 <= numero_pagina <= len(leitor.pages):
        raise ArquivoIndisponivel(f"{hash_sha256}#{numero_pagina}")
    escritor = PdfWriter()
    escritor.add_page(leitor.pages[numero_pagina - 1])
    buffer = io.BytesIO()
    escritor.write(buffer)
    return buffer.getvalue()
