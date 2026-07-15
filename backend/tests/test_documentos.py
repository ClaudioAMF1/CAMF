import pytest

from app.services.documentos import (
    formatar_cpf_cnpj,
    normalizar_cpf_cnpj,
    normalizar_nome,
    somente_digitos,
    validar_cnpj,
    validar_cpf,
)


def test_somente_digitos():
    assert somente_digitos("42.800.118/0001-44") == "42800118000144"
    assert somente_digitos(None) == ""


@pytest.mark.parametrize("cpf", ["529.982.247-25", "52998224725"])
def test_cpf_valido(cpf):
    assert validar_cpf(cpf)


@pytest.mark.parametrize("cpf", ["111.111.111-11", "529.982.247-26", "123", ""])
def test_cpf_invalido(cpf):
    assert not validar_cpf(cpf)


@pytest.mark.parametrize("cnpj", ["42.800.118/0001-44", "11.222.333/0001-81"])
def test_cnpj_valido(cnpj):
    assert validar_cnpj(cnpj)


@pytest.mark.parametrize("cnpj", ["11.111.111/1111-11", "42.800.118/0001-45", "123"])
def test_cnpj_invalido(cnpj):
    assert not validar_cnpj(cnpj)


def test_normalizar_cpf_cnpj():
    assert normalizar_cpf_cnpj("42.800.118/0001-44") == "42800118000144"
    assert normalizar_cpf_cnpj("529.982.247-25") == "52998224725"
    assert normalizar_cpf_cnpj("42.800.118/0001-45") is None  # DV errado
    assert normalizar_cpf_cnpj("") is None
    assert normalizar_cpf_cnpj(None) is None


def test_formatar_cpf_cnpj():
    assert formatar_cpf_cnpj("42800118000144") == "42.800.118/0001-44"
    assert formatar_cpf_cnpj("52998224725") == "529.982.247-25"


def test_normalizar_nome():
    assert normalizar_nome("  João   da  Silva Júnior ") == "JOAO DA SILVA JUNIOR"
    assert normalizar_nome("CAMF Construtora LTDA") == "CAMF CONSTRUTORA LTDA"
