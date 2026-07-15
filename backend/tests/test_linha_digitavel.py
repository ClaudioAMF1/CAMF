from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.services.linha_digitavel import (
    BASE_2025,
    analisar,
    data_para_fator,
    dv_modulo10,
    dv_modulo11,
    fator_para_data,
    linha_para_codigo_barras,
    montar_linha,
    normalizar_linha,
    validar_dv_geral,
    validar_dvs_campos,
)

# Exemplo clássico FEBRABAN (Banco do Brasil): valor R$ 1,00, venc. 31/12/2007
LINHA_CLASSICA = "00190500954014481606906809350314337370000000100"
BARRAS_CLASSICO = "00193373700000001000500940144816060680935031"


def test_normalizar_linha_remove_pontuacao():
    formatada = "00190.50095 40144.816069 06809.350314 3 37370000000100"
    assert normalizar_linha(formatada) == LINHA_CLASSICA


def test_normalizar_linha_invalida():
    assert normalizar_linha("123") is None
    assert normalizar_linha(None) is None
    assert normalizar_linha("") is None


def test_conversao_para_codigo_barras():
    assert linha_para_codigo_barras(LINHA_CLASSICA) == BARRAS_CLASSICO


def test_dv_modulo10_campos_classicos():
    assert dv_modulo10("001905009") == 5
    assert dv_modulo10("4014481606") == 9
    assert dv_modulo10("0680935031") == 4


def test_dv_modulo11_geral():
    sem_dv = BARRAS_CLASSICO[0:4] + BARRAS_CLASSICO[5:]
    assert dv_modulo11(sem_dv) == 3
    assert validar_dv_geral(BARRAS_CLASSICO)


def test_dvs_campos_validos():
    assert validar_dvs_campos(LINHA_CLASSICA)


def test_dv_campo_invalido_detectado():
    corrompida = LINHA_CLASSICA[:9] + "0" + LINHA_CLASSICA[10:]  # DV campo 1 errado
    assert not validar_dvs_campos(corrompida)


def test_analisar_extrai_valor_e_vencimento():
    resultado = analisar(LINHA_CLASSICA, referencia=date(2008, 1, 1))
    assert resultado is not None
    assert resultado.codigo_barras == BARRAS_CLASSICO
    assert resultado.valor == Decimal("1.00")
    assert resultado.vencimento == date(2007, 12, 31)
    assert resultado.erros == []


def test_analisar_detecta_dv_geral_invalido():
    corrompida = LINHA_CLASSICA[:32] + "9" + LINHA_CLASSICA[33:]
    resultado = analisar(corrompida, referencia=date(2008, 1, 1))
    assert "dv_geral_invalido" in resultado.erros


@pytest.mark.parametrize(
    ("fator", "referencia", "esperado"),
    [
        (9999, date(2025, 1, 1), date(2025, 2, 21)),   # último dia do ciclo antigo
        (1000, date(2000, 7, 1), date(2000, 7, 3)),    # ciclo antigo
        (1000, date(2026, 7, 15), date(2025, 2, 22)),  # reinício pós-2025
        (500, date(2026, 7, 15), BASE_2025 + timedelta(days=500)),
        (0, date(2026, 7, 15), None),
    ],
)
def test_fator_para_data(fator, referencia, esperado):
    assert fator_para_data(fator, referencia) == esperado


def test_data_para_fator_e_volta():
    vencimento = date(2026, 8, 10)
    fator = data_para_fator(vencimento)
    assert 1000 <= fator <= 9999
    assert fator_para_data(fator, referencia=date(2026, 7, 15)) == vencimento


def test_montar_linha_round_trip():
    vencimento = date(2026, 8, 10)
    valor = Decimal("10985.00")
    linha = montar_linha(valor=valor, vencimento=vencimento)
    assert len(linha) == 47
    resultado = analisar(linha, referencia=date(2026, 7, 15))
    assert resultado.erros == []
    assert resultado.banco == "756"
    assert resultado.valor == valor
    assert resultado.vencimento == vencimento
