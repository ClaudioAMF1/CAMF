"""Exportações no layout dos relatórios que a CAMF já usa no papel.

- Parcelas em aberto: agrupado por data de vencimento, com "Total Cedente" e
  "Total por Data de Vencimento", como o relatório de parcelas do Sicoob.
- Relação de títulos: lista corrida com Tipo, DOC, valor nominal/disponível,
  vencimento, taxa de juros e pagador.

Os dois saem em PDF (para imprimir) e em XLSX (para trabalhar a planilha).
O cabeçalho identifica a CAMF como emissora: o layout é o mesmo, mas o
documento não se passa por um relatório emitido pelo banco.
"""

import io
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from ..config import settings
from . import linha_digitavel
from .relatorios import ambiente_templates

ZERO = Decimal("0.00")


# --- Cedente (código do beneficiário no Sicoob) -----------------------------

@dataclass
class Cedente:
    codigo: str        # "185879-3"
    cooperativa: str   # "5004"
    nome: str


def campo_livre_sicoob(linha: str | None) -> dict | None:
    """Decompõe o campo livre do boleto Sicoob (756).

    Layout das 25 posições: carteira(1) cooperativa(4) modalidade(2)
    código do beneficiário(7, o último é o DV) nosso número(8) parcela(3).
    """
    linha = linha_digitavel.normalizar_linha(linha)
    if not linha or not linha.startswith("756"):
        return None
    livre = linha_digitavel.linha_para_codigo_barras(linha)[19:]
    cliente = livre[7:14]
    if not int(cliente):
        return None  # campo livre fora do padrão da cobrança Sicoob
    return {
        "cooperativa": livre[1:5],
        "cedente": f"{int(cliente[:-1])}-{cliente[-1]}",
    }


def identificar_cedente(df: pd.DataFrame) -> Cedente:
    """O cedente mais frequente entre os boletos (normalmente há um só)."""
    contagem = Counter()
    if not df.empty:
        for linha in df["linha_digitavel"]:
            info = campo_livre_sicoob(_texto(linha))
            if info:
                contagem[(info["cedente"], info["cooperativa"])] += 1
    codigo, cooperativa = contagem.most_common(1)[0][0] if contagem else ("", "")
    return Cedente(codigo=codigo, cooperativa=cooperativa, nome=settings.empresa_nome.upper())


# --- Montagem dos dados ------------------------------------------------------

def _texto(valor) -> str:
    """None e NaN (o pandas troca None por NaN em colunas mistas) viram ''."""
    return "" if valor is None or pd.isna(valor) else str(valor)


def _data(valor) -> date | None:
    return None if valor is None or pd.isna(valor) else valor


def _dec(valor) -> Decimal:
    return Decimal(str(valor)).quantize(Decimal("0.01"))


def _ordem_numero(texto) -> tuple:
    """'51-03' -> (51, 3): ordena pela sequência do banco, não como texto."""
    numeros = [int(n) for n in re.findall(r"\d+", _texto(texto))]
    return (0, *numeros) if numeros else (1,)


def periodo_dos_dados(df: pd.DataFrame, de: date | None, ate: date | None) -> str:
    """Período do cabeçalho: o do filtro, ou o intervalo real dos vencimentos."""
    if df.empty and not (de or ate):
        return ""
    vencimentos = df["vencimento"].dropna() if not df.empty else pd.Series(dtype=object)
    inicio = de or (vencimentos.min() if len(vencimentos) else None)
    fim = ate or (vencimentos.max() if len(vencimentos) else None)
    if inicio and fim:
        return f"{inicio:%d/%m/%Y} a {fim:%d/%m/%Y}"
    return ""


def montar_parcelas_em_aberto(df: pd.DataFrame) -> dict:
    """Agrupa por data de vencimento, como no relatório de parcelas do banco."""
    grupos = []
    if not df.empty:
        abertos = df[df["vencimento"].notna()]
        for vencimento, bloco in sorted(abertos.groupby("vencimento"), key=lambda g: g[0]):
            itens = []
            registros = sorted(
                bloco.to_dict("records"),
                key=lambda r: (_ordem_numero(r.get("nosso_numero")), _texto(r.get("pagador_nome"))),
            )
            for r in registros:
                valor = _dec(r["valor"])
                pago_parcial = ZERO  # o sistema não registra pagamento parcial
                itens.append({
                    "sacado": _texto(r.get("pagador_nome")),
                    "nosso_numero": _texto(r.get("nosso_numero")),
                    "seu_numero": _texto(r.get("num_documento")),
                    "docto": _texto(r.get("especie")) or "DM",
                    "vencimento": vencimento,
                    "valor": valor,
                    "pago_parcial": pago_parcial,
                    "saldo": valor - pago_parcial,
                })
            grupos.append({
                "vencimento": vencimento,
                "itens": itens,
                "total_valor": sum((i["valor"] for i in itens), ZERO),
                "total_pago": sum((i["pago_parcial"] for i in itens), ZERO),
                "total_saldo": sum((i["saldo"] for i in itens), ZERO),
            })
    return {
        "grupos": grupos,
        "qtd": sum(len(g["itens"]) for g in grupos),
        "total_valor": sum((g["total_valor"] for g in grupos), ZERO),
        "total_pago": sum((g["total_pago"] for g in grupos), ZERO),
        "total_saldo": sum((g["total_saldo"] for g in grupos), ZERO),
    }


def montar_titulos(df: pd.DataFrame, taxa: Decimal | None) -> dict:
    """Lista corrida por vencimento: Tipo, DOC, valores, vencimento, taxa, pagador."""
    itens = []
    if not df.empty:
        registros = sorted(
            df.to_dict("records"),
            key=lambda r: (_data(r.get("vencimento")) or date.max, _ordem_numero(r.get("nosso_numero"))),
        )
        for r in registros:
            valor = _dec(r["valor"])
            itens.append({
                "tipo": "Boleto",
                "doc": _texto(r.get("nosso_numero")) or _texto(r.get("num_documento")),
                "valor_nominal": valor,
                # sem desconto aplicado, o disponível é o próprio nominal
                "valor_disponivel": valor,
                "vencimento": _data(r.get("vencimento")),
                "taxa": taxa,
                "pagador": _texto(r.get("pagador_nome")),
            })
    return {
        "itens": itens,
        "qtd": len(itens),
        "total_nominal": sum((i["valor_nominal"] for i in itens), ZERO),
        "total_disponivel": sum((i["valor_disponivel"] for i in itens), ZERO),
    }


# --- Formatação --------------------------------------------------------------

def formatar_numero(valor) -> str:
    """1234.5 -> '1.234,50' (sem R$, como no relatório do banco)."""
    if valor is None:
        return ""
    texto = f"{Decimal(str(valor)):,.2f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


def formatar_taxa(valor) -> str:
    """1.69 -> '1,6900 %'."""
    if valor is None:
        return ""
    return f"{Decimal(str(valor)):.4f}".replace(".", ",") + " %"


def _render_pdf(nome_template: str, **contexto) -> bytes:
    from weasyprint import HTML

    env = ambiente_templates()
    env.filters["num_br"] = formatar_numero
    env.filters["taxa"] = formatar_taxa
    html = env.get_template(nome_template).render(
        empresa=settings.empresa_nome,
        cnpj=settings.empresa_cnpj,
        emitido_em=datetime.now(),
        **contexto,
    )
    return HTML(string=html).write_pdf()


# --- Parcelas em aberto ------------------------------------------------------

def gerar_parcelas_pdf(df: pd.DataFrame, periodo: str) -> bytes:
    return _render_pdf(
        "parcelas_aberto.html",
        dados=montar_parcelas_em_aberto(df),
        cedente=identificar_cedente(df),
        periodo=periodo,
    )


CINZA_FAIXA = PatternFill("solid", fgColor="D0D0D0")    # cabeçalho e cedente
CINZA_LISTRA = PatternFill("solid", fgColor="EDEDED")   # linhas alternadas
CINZA_TOTAL = PatternFill("solid", fgColor="DCDCDC")    # Total Cedente
CINZA_DATA = PatternFill("solid", fgColor="C4C4C4")     # Total por Data
CINZA_GERAL = PatternFill("solid", fgColor="A9A9A9")    # Total Geral
FORMATO_NUM = "#,##0.00"
FORMATO_DATA = "DD/MM/YYYY"


def _preencher(ws, linha: int, ate_coluna: int, fill: PatternFill) -> None:
    for col in range(1, ate_coluna + 1):
        ws.cell(row=linha, column=col).fill = fill


def gerar_parcelas_xlsx(df: pd.DataFrame, periodo: str) -> bytes:
    dados = montar_parcelas_em_aberto(df)
    cedente = identificar_cedente(df)
    agora = datetime.now()

    wb = Workbook()
    ws = wb.active
    ws.title = "Parcelas em aberto"
    ncols = 9
    negrito = Font(bold=True)
    direita = Alignment(horizontal="right")

    # Cabeçalho do documento
    ws.append([settings.empresa_nome.upper(), None, None, "RELATÓRIO DE PARCELAS EM ABERTO",
               None, None, None, "Data de Emissão:", f"{agora:%d/%m/%Y}"])
    ws.append([f"CNPJ {settings.empresa_cnpj}", None, None,
               _linha_sicoob(cedente), None, None, None, "Hora de Emissão:", f"{agora:%H:%M:%S}"])
    ws.append([f"Período: {periodo}" if periodo else None])
    for linha in (1, 2):
        ws.cell(row=linha, column=1).font = negrito
        ws.cell(row=linha, column=8).alignment = direita
    ws.cell(row=1, column=4).font = Font(bold=True, size=12)
    ws.append([])

    # Cabeçalho das colunas (duas linhas, como no relatório: Nome / Sacado)
    titulos = ["Cedente", "Nome", "Nosso Nº", "Seu Número", "Docto", "Vencimento",
               "Valor Operação", "Valor Pago Parcial", "Saldo Devedor"]
    ws.append(titulos)
    ws.append([None, "Sacado"])
    for linha in (ws.max_row - 1, ws.max_row):
        _preencher(ws, linha, ncols, CINZA_FAIXA)
        for col in range(1, ncols + 1):
            ws.cell(row=linha, column=col).font = negrito
            ws.cell(row=linha, column=col).alignment = Alignment(
                horizontal="right" if col >= 7 else "left", vertical="bottom", wrap_text=True)
    ws.freeze_panes = ws.cell(row=ws.max_row + 1, column=1)
    linha_titulos = ws.max_row - 1

    for grupo in dados["grupos"]:
        ws.append([cedente.codigo, cedente.nome])
        _preencher(ws, ws.max_row, ncols, CINZA_FAIXA)
        ws.cell(row=ws.max_row, column=1).font = negrito
        ws.cell(row=ws.max_row, column=2).font = negrito

        for idx, item in enumerate(grupo["itens"]):
            ws.append([None, item["sacado"], item["nosso_numero"], item["seu_numero"],
                       item["docto"], item["vencimento"], item["valor"],
                       item["pago_parcial"], item["saldo"]])
            ws.cell(row=ws.max_row, column=6).number_format = FORMATO_DATA
            for col in (7, 8, 9):
                ws.cell(row=ws.max_row, column=col).number_format = FORMATO_NUM
            if idx % 2:
                _preencher(ws, ws.max_row, ncols, CINZA_LISTRA)

        _linha_total(ws, "Total Cedente:", None, grupo, CINZA_TOTAL, ncols)
        _linha_total(ws, "Total por Data de Vencimento:", grupo["vencimento"], grupo,
                     CINZA_DATA, ncols)

    ws.append([])
    ws.append([None, f'Total Geral ({dados["qtd"]} parcela(s)):', None, None, None, None,
               dados["total_valor"], dados["total_pago"], dados["total_saldo"]])
    ws.merge_cells(start_row=ws.max_row, start_column=2, end_row=ws.max_row, end_column=6)
    ws.cell(row=ws.max_row, column=2).alignment = direita
    _preencher(ws, ws.max_row, ncols, CINZA_GERAL)
    for col in range(1, ncols + 1):
        celula = ws.cell(row=ws.max_row, column=col)
        celula.font = negrito
        if col >= 7:
            celula.number_format = FORMATO_NUM

    for col, largura in enumerate((11, 42, 11, 12, 7, 12, 15, 15, 15), start=1):
        ws.column_dimensions[get_column_letter(col)].width = largura

    _configurar_impressao(ws, linha_titulos, retrato=True)
    return _salvar(wb)


def _linha_sicoob(cedente: Cedente) -> str:
    partes = ["Sicoob"]
    if cedente.cooperativa:
        partes.append(f"Cooperativa {cedente.cooperativa}")
    if cedente.codigo:
        partes.append(f"Cedente {cedente.codigo}")
    return " · ".join(partes)


def _linha_total(ws, rotulo, vencimento, grupo, fill, ncols) -> None:
    # rótulo em B:E mesclado e alinhado à direita, encostado nos valores
    ws.append([None, rotulo, None, None, None, vencimento,
               grupo["total_valor"], grupo["total_pago"], grupo["total_saldo"]])
    linha = ws.max_row
    ws.merge_cells(start_row=linha, start_column=2, end_row=linha, end_column=5)
    ws.cell(row=linha, column=2).alignment = Alignment(horizontal="right")
    _preencher(ws, linha, ncols, fill)
    for col in range(2, ncols + 1):
        ws.cell(row=linha, column=col).font = Font(bold=True)
    ws.cell(row=linha, column=6).number_format = FORMATO_DATA
    for col in (7, 8, 9):
        ws.cell(row=linha, column=col).number_format = FORMATO_NUM


# --- Relação de títulos ------------------------------------------------------

def gerar_titulos_pdf(df: pd.DataFrame, taxa: Decimal | None, periodo: str) -> bytes:
    return _render_pdf("titulos.html", dados=montar_titulos(df, taxa), periodo=periodo)


def gerar_titulos_xlsx(df: pd.DataFrame, taxa: Decimal | None) -> bytes:
    dados = montar_titulos(df, taxa)
    wb = Workbook()
    ws = wb.active
    ws.title = "Títulos"
    negrito = Font(bold=True)
    fina = Side(style="thin", color="BFBFBF")

    titulos = ["Tipo", "DOC", "Valor nominal", "Valor Disponível", "Vencimento",
               "Tx.Juros", "Pagador"]
    ws.append(titulos)
    for col in range(1, len(titulos) + 1):
        celula = ws.cell(row=1, column=col)
        celula.font = negrito
        celula.border = Border(bottom=fina)
        celula.alignment = Alignment(horizontal="center" if col < 7 else "left")
    ws.freeze_panes = "A2"

    for item in dados["itens"]:
        # a taxa vai como fração (1,69% -> 0,0169) para o Excel calcular com ela
        taxa_cel = item["taxa"] / 100 if item["taxa"] is not None else None
        ws.append([item["tipo"], item["doc"], item["valor_nominal"], item["valor_disponivel"],
                   item["vencimento"], taxa_cel, item["pagador"]])
        linha = ws.max_row
        ws.cell(row=linha, column=3).number_format = 'R$ #,##0.00'
        ws.cell(row=linha, column=4).number_format = 'R$ #,##0.00'
        ws.cell(row=linha, column=5).number_format = FORMATO_DATA
        ws.cell(row=linha, column=6).number_format = "0.0000 %"
        for col in (1, 2, 5, 6):
            ws.cell(row=linha, column=col).alignment = Alignment(horizontal="center")

    ws.append([])
    ws.append(["Total", f'{dados["qtd"]} título(s)', dados["total_nominal"],
               dados["total_disponivel"]])
    for col in range(1, 5):
        celula = ws.cell(row=ws.max_row, column=col)
        celula.font = negrito
        celula.border = Border(top=fina)
        if col in (3, 4):
            celula.number_format = 'R$ #,##0.00'

    for col, largura in enumerate((10, 16, 16, 18, 13, 11, 48), start=1):
        ws.column_dimensions[get_column_letter(col)].width = largura

    _configurar_impressao(ws, 1, retrato=False)
    return _salvar(wb)


# --- Utilidades --------------------------------------------------------------

def _configurar_impressao(ws, linha_titulos: int, retrato: bool) -> None:
    """A planilha impressa sai como o PDF: A4, uma página de largura,
    com o cabeçalho das colunas repetido em toda folha."""
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.orientation = "portrait" if retrato else "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = f"{linha_titulos}:{linha_titulos + (1 if retrato else 0)}"
    ws.page_margins.left = ws.page_margins.right = 0.4


def _salvar(wb: Workbook) -> bytes:
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
