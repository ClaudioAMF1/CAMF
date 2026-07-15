from datetime import date
from decimal import Decimal

from app.services.extracao import (
    eh_linha_rotulo,
    extrair_dados_pagina,
    _nome_na_linha,
)
from app.services.linha_digitavel import montar_linha

from .conftest import formatar_linha


def test_linha_de_rotulos_e_reconhecida():
    assert eh_linha_rotulo("Nome do pagador Número do Documento")
    assert eh_linha_rotulo("CPF/CNPJ Vencimento Valor do Documento")
    assert eh_linha_rotulo("Agência/Código Beneficiário Nosso Número")
    assert not eh_linha_rotulo("MARIA APARECIDA DE SOUZA")
    assert not eh_linha_rotulo("JOAO DA SILVA 529.982.247-25")


def test_nome_corta_no_primeiro_token_de_dado():
    assert _nome_na_linha("MARIA OLIVEIRA 7-02 529.982.247-25 10/08/2026") == "MARIA OLIVEIRA"
    assert _nome_na_linha("JOAO DA SILVA CPF/CNPJ: 529.982.247-25") == "JOAO DA SILVA"
    assert _nome_na_linha("EMPRESA XYZ LTDA 11.222.333/0001-81 1.250,00") == "EMPRESA XYZ LTDA"


def test_layout_tabular_rotulos_e_valores_em_linhas_separadas():
    """Layout real do Sicoob: linha de rótulos seguida da linha de valores."""
    linha = montar_linha(
        campo_livre="9" * 25, valor=Decimal("1250.00"), vencimento=date(2026, 8, 10)
    )
    texto = f"""SICOOB 756-0
Local de Pagamento PAGÁVEL PREFERENCIALMENTE NAS COOPERATIVAS DO SICOOB
Beneficiário CAMF CONSTRUTORA LTDA CNPJ: 42.800.118/0001-44
Data do Documento Nº do Documento Espécie Doc. Aceite Vencimento
01/06/2026 12-04 DM N 10/08/2026
Carteira Nosso Número (=) Valor do Documento
1 1-1 1.250,00
Pagador
Nome do pagador Número do Documento
MARIA APARECIDA DE SOUZA 12-04
CPF/CNPJ
529.982.247-25
RUA DAS ACÁCIAS, 45
JARDIM AMÉRICA BELO HORIZONTE - MG 30310-000
Ficha de Compensação
{formatar_linha(linha)}
"""
    dados = extrair_dados_pagina(texto)
    assert dados is not None
    assert dados.pagador_nome == "MARIA APARECIDA DE SOUZA"
    assert dados.pagador_cpf_cnpj == "529.982.247-25"
    assert dados.vencimento == date(2026, 8, 10)
    assert dados.valor == Decimal("1250.00")
    assert dados.num_documento == "12-04"
    assert dados.cep == "30310000"


def test_cnpj_do_beneficiario_nao_vira_documento_do_pagador():
    linha = montar_linha(
        campo_livre="8" * 25, valor=Decimal("500.00"), vencimento=date(2026, 9, 1)
    )
    texto = f"""SICOOB
Beneficiário CAMF CONSTRUTORA LTDA CNPJ: 42.800.118/0001-44
Vencimento 01/09/2026
(=) Valor do Documento 500,00
Pagador
FULANO DE TAL
42.800.118/0001-44
{formatar_linha(linha)}
"""
    dados = extrair_dados_pagina(texto)
    assert dados.pagador_nome == "FULANO DE TAL"
    # único documento no bloco é o do beneficiário -> pagador fica sem documento
    assert dados.pagador_cpf_cnpj is None
