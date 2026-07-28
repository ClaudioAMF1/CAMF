from datetime import date
from decimal import Decimal

from app.services.extracao import (
    eh_linha_rotulo,
    extrair_dados_pagina,
    _nome_na_linha,
    _nome_valido,
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


def test_nome_valido_rejeita_rotulos():
    # o bug dos screenshots: uma sequência de rótulos nunca vira nome
    assert _nome_valido("Nome do pagador Número do Documento") is None
    assert _nome_valido("Nome do Pagador") is None
    assert _nome_valido("CPF/CNPJ do Pagador") is None
    assert _nome_valido("Endereço") is None
    assert _nome_valido("") is None
    assert _nome_valido(None) is None


def test_nome_valido_aceita_e_limpa_nomes_reais():
    assert _nome_valido("JOAO DA SILVA") == "JOAO DA SILVA"
    assert _nome_valido("MARIA APARECIDA DE SOUZA") == "MARIA APARECIDA DE SOUZA"
    # rótulo grudado no começo do nome (layout tabular) é removido
    assert _nome_valido("Nome do pagador JOAO DA SILVA") == "JOAO DA SILVA"
    assert _nome_valido("Pagador CONSTRUTORA XYZ LTDA") == "CONSTRUTORA XYZ LTDA"


def test_pagina_com_linha_de_rotulos_nao_gera_nome_lixo():
    """Se só há linha de rótulos como nome, o pagador fica sem nome (revisão),
    e nunca com o texto do rótulo."""
    linha = montar_linha(campo_livre="7" * 25, valor=Decimal("100.00"), vencimento=date(2026, 8, 10))
    texto = f"""SICOOB
Beneficiário CAMF CONSTRUTORA LTDA CNPJ: 42.800.118/0001-44
Vencimento 10/08/2026
(=) Valor do Documento 100,00
Pagador
Nome do pagador Número do Documento
{formatar_linha(linha)}
"""
    dados = extrair_dados_pagina(texto)
    assert dados.pagador_nome is None


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


# Texto real de um boleto Sicoob (banco 756) extraído pelo pdfplumber:
# dois blocos "Pagador" (recibo + ficha), rótulos e valores em linhas separadas,
# cidade/UF/CEP sem hífen, e a linha digitável real (DVs válidos).
TEXTO_SICOOB_REAL = """Beneficiário Vencimento Valor do Documento
CAMF CONSTRUTORA LTDA 42.800.118/0001-44 20/09/2026 9.600,00
6 - S/N (+) Outros acréscimos (+) Mora / Multa
LOTEAMENTO FECHADO LE PARC
(-) Desconto / Abatimento (-) Outras deduções
Luziânia - GO 72812-762
Instruções (texto de responsabilidade do beneficiário) Data de Emissão (=) Valor cobrado
Não cobrar encargos por atraso. 27/07/2026
Não conceder desconto. Coop Contr/Cód. Beneficiário
5004/1858793
Nosso Número
9-4
Dados do Pagador
Nome do pagador Número do Documento
JANICIO DE CARVALHO 70-01
Endereço
AVENIDA LIGIA DE OLIVEIRA MACHADO
Bairro / Distrito
RESIDENCIAL ALTO DAS CARAÍBAS
Munícipio UF CEP
LUZIANIA GO 72813-105
Mensagem Pagador
Autenticação mecânica - Recibo do pagador
756 75691.50043 01185.879309 00000.940015 2 15750000960000
Local de pagamento Vencimento
PAGAVEL PREFERENCIALMENTE NO SICOOB 20/09/2026
Beneficiário Cooperativa contratante/Cód. Beneficiário
CAMF CONSTRUTORA LTDA 42.800.118/0001-44 5004/1858793
Data do documento N. documento Espécie Aceite Data processamento Nosso número
27/07/2026 70-01 DM N 27/07/2026 9-4
Uso do Banco Carteira Espécie Quantidade Valor Valor documento
1 R$ 0,00 9.600,00
Pagador (+) Outros acréscimos
JANICIO DE CARVALHO 053.900.981-45
AVENIDA LIGIA DE OLIVEIRA MACHADO
RESIDENCIAL ALTO DAS CARAÍBAS (=) Valor cobrado
LUZIANIA - GO 72813-105
Beneficiário final CAMF CONSTRUTORA LTDA 42.800.118/0001-44
Autenticação mecânica - Ficha de compensação
"""


def test_boleto_sicoob_real_extrai_pagador_completo():
    """Regressão do layout real: nome, CPF (em bloco separado do nome),
    endereço e cidade/UF/CEP sem hífen são todos reconhecidos."""
    dados = extrair_dados_pagina(TEXTO_SICOOB_REAL)
    assert dados is not None
    assert dados.pagador_nome == "JANICIO DE CARVALHO"
    assert dados.pagador_cpf_cnpj == "053.900.981-45"  # CPF do bloco da ficha
    assert dados.endereco == "AVENIDA LIGIA DE OLIVEIRA MACHADO"
    assert dados.bairro == "RESIDENCIAL ALTO DAS CARAÍBAS"
    assert dados.municipio == "LUZIANIA"
    assert dados.uf == "GO"
    assert dados.cep == "72813105"
    assert dados.num_documento == "70-01"
    assert dados.nosso_numero == "9-4"
    assert dados.vencimento == date(2026, 9, 20)
    assert dados.valor == Decimal("9600.00")
    assert dados.beneficiario_nome == "CAMF CONSTRUTORA LTDA"
    assert dados.beneficiario_cnpj == "42.800.118/0001-44"


def test_boleto_real_sem_divergencias_de_validacao():
    from app.services.linha_digitavel import analisar

    dados = extrair_dados_pagina(TEXTO_SICOOB_REAL)
    analise = analisar(dados.linha_digitavel_bruta)
    assert analise is not None
    assert analise.erros == []
    assert analise.valor == dados.valor
    assert analise.vencimento == dados.vencimento


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
