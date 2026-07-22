#!/usr/bin/env python3
"""Diagnóstico de extração de um PDF de boleto Sicoob.

Uso:
    python backend/scripts/diagnosticar.py caminho/para/boleto.pdf

Imprime, por página: o texto bruto que o pdfplumber extrai e os campos que o
parser reconheceu. Cole a saída (ou só o TEXTO BRUTO de uma página) para que o
parser seja calibrado ao layout real do seu boleto.
"""
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import extracao, linha_digitavel  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    conteudo = Path(sys.argv[1]).read_bytes()
    textos = extracao.extrair_textos_paginas(conteudo)
    print(f"# {len(textos)} página(s)\n")

    for num, texto in enumerate(textos, start=1):
        print("=" * 70)
        print(f"PÁGINA {num}")
        print("=" * 70)
        print("\n--- TEXTO BRUTO EXTRAÍDO ---")
        print(texto or "(sem texto)")

        dados = extracao.extrair_dados_pagina(texto)
        print("\n--- CAMPOS RECONHECIDOS ---")
        if dados is None:
            marcador = " (parece boleto!)" if extracao.parece_boleto(texto) else ""
            print(f"Sem linha digitável reconhecida — página ignorada{marcador}")
            continue
        analise = linha_digitavel.analisar(dados.linha_digitavel_bruta)
        for chave, valor in asdict(dados).items():
            print(f"  {chave:22} = {valor!r}")
        if analise is not None:
            print(f"  {'valor_da_linha':22} = {analise.valor!r}")
            print(f"  {'vencimento_da_linha':22} = {analise.vencimento!r}")
            print(f"  {'erros_validacao':22} = {analise.erros!r}")
        print()


if __name__ == "__main__":
    main()
