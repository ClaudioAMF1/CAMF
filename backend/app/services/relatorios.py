"""Geração de relatórios PDF (WeasyPrint), XLSX (openpyxl) e CSV."""

import csv
import io
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from ..config import settings

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
FORMATO_BRL = 'R$ #,##0.00'


def formatar_brl(valor) -> str:
    if valor is None:
        return ""
    num = f"{Decimal(str(valor)):,.2f}"
    return "R$ " + num.replace(",", "_").replace(".", ",").replace("_", ".")


def formatar_data(valor) -> str:
    return f"{valor:%d/%m/%Y}" if valor else ""


def gerar_pdf(df: pd.DataFrame, resumo: dict, periodo: str) -> bytes:
    from weasyprint import HTML

    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    env.filters["brl"] = formatar_brl
    env.filters["data_br"] = formatar_data
    template = env.get_template("relatorio.html")

    detalhado = df.sort_values(["pagador_nome", "vencimento"]).to_dict("records") if not df.empty else []
    html = template.render(
        empresa=settings.empresa_nome,
        cnpj=settings.empresa_cnpj,
        gerado_em=datetime.now(),
        periodo=periodo,
        resumo=resumo,
        detalhado=detalhado,
    )
    return HTML(string=html).write_pdf()


COLUNAS_DETALHADO = [
    ("ID", "id", 8),
    ("Pagador", "pagador_nome", 38),
    ("CPF/CNPJ", "pagador_cpf_cnpj", 18),
    ("Nº Documento", "num_documento", 14),
    ("Nosso Número", "nosso_numero", 14),
    ("Emissão", "data_emissao", 12),
    ("Vencimento", "vencimento", 12),
    ("Valor", "valor", 14),
    ("Situação", "situacao", 12),
    ("Qualidade", "qualidade", 16),
    ("Vencido", "vencido", 10),
    ("Data Pagamento", "data_pagamento", 14),
    ("Valor Pago", "valor_pago", 14),
    ("Divergências", "divergencias", 30),
    ("Linha Digitável", "linha_digitavel", 50),
    ("Observação", "observacao", 30),
]


def gerar_xlsx(df: pd.DataFrame, resumo: dict) -> bytes:
    wb = Workbook()
    negrito = Font(bold=True)
    cabecalho_fill = PatternFill("solid", fgColor="1F4E78")
    cabecalho_font = Font(bold=True, color="FFFFFF")

    # --- Aba Resumo: pagador × valor unitário ---
    ws = wb.active
    ws.title = "Resumo"
    ws.append(["Pagador", "Qtd", "Valor Unitário", "Subtotal"])
    for col in range(1, 5):
        celula = ws.cell(row=1, column=col)
        celula.fill = cabecalho_fill
        celula.font = cabecalho_font
    for item in resumo["por_pagador"]:
        ws.append([item["nome"], item["qtd"], item["valor_unitario"], item["subtotal"]])
        ws.cell(row=ws.max_row, column=3).number_format = FORMATO_BRL
        ws.cell(row=ws.max_row, column=4).number_format = FORMATO_BRL
    ws.append(["TOTAL GERAL", resumo["qtd_boletos"], None, resumo["total_geral"]])
    for col in range(1, 5):
        ws.cell(row=ws.max_row, column=col).font = negrito
    ws.cell(row=ws.max_row, column=4).number_format = FORMATO_BRL
    for col, largura in zip(range(1, 5), (40, 8, 16, 16)):
        ws.column_dimensions[get_column_letter(col)].width = largura
    ws.freeze_panes = "A2"

    # --- Aba Detalhado ---
    ws2 = wb.create_sheet("Detalhado")
    ws2.append([titulo for titulo, _, _ in COLUNAS_DETALHADO])
    for col in range(1, len(COLUNAS_DETALHADO) + 1):
        celula = ws2.cell(row=1, column=col)
        celula.fill = cabecalho_fill
        celula.font = cabecalho_font
        celula.alignment = Alignment(horizontal="center")
    registros = df.to_dict("records") if not df.empty else []
    for registro in registros:
        linha = []
        for _, chave, _ in COLUNAS_DETALHADO:
            valor = registro.get(chave)
            if chave in ("data_emissao", "vencimento", "data_pagamento"):
                valor = formatar_data(valor)
            elif chave == "vencido":
                valor = "sim" if valor else "não"
            elif valor is not None and not isinstance(valor, (str, int, float, Decimal)):
                valor = str(valor)
            linha.append(valor)
        ws2.append(linha)
        for idx, (_, chave, _) in enumerate(COLUNAS_DETALHADO, start=1):
            if chave in ("valor", "valor_pago"):
                ws2.cell(row=ws2.max_row, column=idx).number_format = FORMATO_BRL
    for idx, (_, _, largura) in enumerate(COLUNAS_DETALHADO, start=1):
        ws2.column_dimensions[get_column_letter(idx)].width = largura
    ws2.freeze_panes = "A2"

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def gerar_csv(df: pd.DataFrame) -> bytes:
    buffer = io.StringIO()
    escritor = csv.writer(buffer, delimiter=";")
    escritor.writerow([titulo for titulo, _, _ in COLUNAS_DETALHADO])
    registros = df.to_dict("records") if not df.empty else []
    for registro in registros:
        linha = []
        for _, chave, _ in COLUNAS_DETALHADO:
            valor = registro.get(chave)
            if chave in ("data_emissao", "vencimento", "data_pagamento"):
                valor = formatar_data(valor)
            elif chave in ("valor", "valor_pago"):
                valor = str(valor).replace(".", ",") if valor is not None else ""
            elif chave == "vencido":
                valor = "sim" if valor else "não"
            linha.append(valor if valor is not None else "")
        escritor.writerow(linha)
    return buffer.getvalue().encode("utf-8-sig")
