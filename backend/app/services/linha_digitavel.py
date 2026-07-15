"""Parser e validação da linha digitável FEBRABAN (47 dígitos).

A linha digitável é a fonte da verdade do boleto: valor, vencimento e
código de barras são derivados dela e comparados com o texto extraído.
"""

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

# Fator de vencimento: base histórica e base do novo ciclo (pós-2025).
# O fator atingiu 9999 em 21/02/2025 e reiniciou em 1000 em 22/02/2025.
BASE_1997 = date(1997, 10, 7)
BASE_2025 = date(2025, 2, 22)

RE_LINHA_FORMATADA = re.compile(
    r"\d{5}\.\d{5}\s+\d{5}\.\d{6}\s+\d{5}\.\d{6}\s+\d\s+\d{14}"
)


def normalizar_linha(texto: str | None) -> str | None:
    """Remove pontuação/espaços; retorna 47 dígitos ou None."""
    digitos = re.sub(r"\D", "", texto or "")
    return digitos if len(digitos) == 47 else None


def linha_para_codigo_barras(linha: str) -> str:
    """Converte linha digitável (47) em código de barras (44).

    Layout do código de barras: banco(3) + moeda(1) + DV geral(1) +
    fator(4) + valor(10) + campo livre(25).
    Na linha digitável: campos 1-3 carregam banco+moeda+campo livre com DVs
    intercalados; posição 32 é o DV geral; posições 33-46 são fator+valor.
    """
    return linha[0:4] + linha[32] + linha[33:47] + linha[4:9] + linha[10:20] + linha[21:31]


def dv_modulo10(sequencia: str) -> int:
    """DV módulo 10 dos campos da linha digitável (pesos 2,1 da direita p/ esquerda)."""
    total = 0
    peso = 2
    for d in reversed(sequencia):
        produto = int(d) * peso
        total += produto if produto < 10 else produto - 9
        peso = 1 if peso == 2 else 2
    return (10 - total % 10) % 10


def dv_modulo11(sequencia: str) -> int:
    """DV geral do código de barras (pesos 2..9 cíclicos da direita p/ esquerda)."""
    total = 0
    peso = 2
    for d in reversed(sequencia):
        total += int(d) * peso
        peso = peso + 1 if peso < 9 else 2
    dv = 11 - (total % 11)
    return 1 if dv in (0, 10, 11) else dv


def validar_dv_geral(codigo_barras: str) -> bool:
    sem_dv = codigo_barras[0:4] + codigo_barras[5:]
    return dv_modulo11(sem_dv) == int(codigo_barras[4])


def validar_dvs_campos(linha: str) -> bool:
    campos = [
        (linha[0:9], int(linha[9])),
        (linha[10:20], int(linha[20])),
        (linha[21:31], int(linha[31])),
    ]
    return all(dv_modulo10(campo) == dv for campo, dv in campos)


def fator_para_data(fator: int, referencia: date | None = None) -> date | None:
    """Converte o fator de vencimento em data.

    Base 07/10/1997. Fatores < 1000 só existem no ciclo novo (base
    22/02/2025). Fatores >= 1000 são ambíguos entre os dois ciclos: escolhe-se
    a data mais próxima da data de referência (hoje, por padrão).
    """
    if fator <= 0:
        return None
    referencia = referencia or date.today()
    if fator < 1000:
        return BASE_2025 + timedelta(days=fator)
    antiga = BASE_1997 + timedelta(days=fator)
    nova = BASE_2025 + timedelta(days=fator - 1000)
    if abs((nova - referencia).days) < abs((antiga - referencia).days):
        return nova
    return antiga


def data_para_fator(vencimento: date, referencia: date | None = None) -> int:
    """Inverso de fator_para_data (útil para testes e montagem de linhas)."""
    referencia = referencia or date.today()
    if vencimento >= BASE_2025:
        return (vencimento - BASE_2025).days + 1000
    return (vencimento - BASE_1997).days


@dataclass
class ResultadoLinha:
    linha_digitavel: str
    codigo_barras: str
    banco: str
    valor: Decimal | None
    vencimento: date | None
    erros: list[str] = field(default_factory=list)


def analisar(linha: str, referencia: date | None = None) -> ResultadoLinha | None:
    """Normaliza, deriva código de barras, valor e vencimento; valida DVs."""
    normalizada = normalizar_linha(linha)
    if normalizada is None:
        return None
    codigo = linha_para_codigo_barras(normalizada)
    erros: list[str] = []

    if not validar_dvs_campos(normalizada):
        erros.append("dv_campo_invalido")
    if not validar_dv_geral(codigo):
        erros.append("dv_geral_invalido")

    valor_centavos = int(codigo[9:19])
    valor = Decimal(valor_centavos) / Decimal(100) if valor_centavos > 0 else None

    fator = int(codigo[5:9])
    vencimento = fator_para_data(fator, referencia)

    return ResultadoLinha(
        linha_digitavel=normalizada,
        codigo_barras=codigo,
        banco=codigo[0:3],
        valor=valor,
        vencimento=vencimento,
        erros=erros,
    )


def montar_linha(
    banco: str = "756",
    moeda: str = "9",
    campo_livre: str = "0" * 25,
    valor: Decimal = Decimal("0"),
    vencimento: date | None = None,
) -> str:
    """Monta uma linha digitável válida (DVs calculados). Usado em testes."""
    fator = data_para_fator(vencimento) if vencimento else 0
    valor_str = str(int(round(valor * 100))).rjust(10, "0")
    fator_str = str(fator).rjust(4, "0")
    corpo_barras_sem_dv = banco + moeda + fator_str + valor_str + campo_livre
    dv_geral = dv_modulo11(corpo_barras_sem_dv)

    campo1 = banco + moeda + campo_livre[0:5]
    campo2 = campo_livre[5:15]
    campo3 = campo_livre[15:25]
    return (
        campo1 + str(dv_modulo10(campo1))
        + campo2 + str(dv_modulo10(campo2))
        + campo3 + str(dv_modulo10(campo3))
        + str(dv_geral)
        + fator_str
        + valor_str
    )
