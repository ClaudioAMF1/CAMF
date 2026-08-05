"""Guarda os PDFs originais para que cada boleto possa ser reaberto.

Os arquivos são gravados por hash SHA-256, então reenviar o mesmo PDF
(inclusive num reprocessamento) não duplica nada em disco.
"""

import io
import logging
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from ..config import settings

logger = logging.getLogger("camf.armazenamento")


class ArquivoIndisponivel(Exception):
    """PDF original não está em disco (ex.: upload feito antes deste recurso)."""


def _raiz() -> Path:
    caminho = Path(settings.armazenamento_dir)
    caminho.mkdir(parents=True, exist_ok=True)
    return caminho


def caminho_do_hash(hash_sha256: str) -> Path:
    return _raiz() / f"{hash_sha256}.pdf"


def guardar(hash_sha256: str, conteudo: bytes) -> None:
    destino = caminho_do_hash(hash_sha256)
    if destino.exists():
        return  # mesmo conteúdo, mesmo arquivo
    try:
        destino.write_bytes(conteudo)
    except OSError:
        # Falha ao gravar não pode derrubar a importação dos boletos
        logger.warning("Não foi possível guardar o PDF %s", hash_sha256, exc_info=True)


def ler(hash_sha256: str) -> bytes:
    caminho = caminho_do_hash(hash_sha256)
    if not caminho.exists():
        raise ArquivoIndisponivel(hash_sha256)
    return caminho.read_bytes()


def extrair_pagina(hash_sha256: str, numero_pagina: int) -> bytes:
    """Devolve um PDF de uma página só — a do boleto pedido (1-indexado)."""
    conteudo = ler(hash_sha256)
    leitor = PdfReader(io.BytesIO(conteudo))
    if not 1 <= numero_pagina <= len(leitor.pages):
        raise ArquivoIndisponivel(f"{hash_sha256}#{numero_pagina}")
    escritor = PdfWriter()
    escritor.add_page(leitor.pages[numero_pagina - 1])
    buffer = io.BytesIO()
    escritor.write(buffer)
    return buffer.getvalue()
