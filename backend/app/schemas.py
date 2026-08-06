from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from .models import Qualidade, Situacao


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Pagador ----------

class PagadorBase(ORMModel):
    id: int
    cpf_cnpj: str | None
    nome: str
    nome_normalizado: str
    endereco: str | None
    bairro: str | None
    municipio: str | None
    uf: str | None
    cep: str | None
    criado_em: datetime
    atualizado_em: datetime
    deletado_em: datetime | None

    @computed_field
    @property
    def provisorio(self) -> bool:
        return self.cpf_cnpj is None


class PagadorOut(PagadorBase):
    nomes_alternativos: list[str] = []
    qtd_boletos: int = 0
    total: Decimal = Decimal("0")


class PagadorPatch(BaseModel):
    nome: str | None = None
    cpf_cnpj: str | None = None
    endereco: str | None = None
    bairro: str | None = None
    municipio: str | None = None
    uf: str | None = None
    cep: str | None = None


class MergeIn(BaseModel):
    pagador_origem_id: int


class SugestaoMerge(BaseModel):
    nome_normalizado: str
    pagadores: list[PagadorBase]


# ---------- Boleto ----------

class BoletoOut(ORMModel):
    id: int
    upload_id: int
    pagador_id: int
    linha_digitavel: str
    codigo_barras: str
    pagina: int | None = None
    nosso_numero: str | None
    num_documento: str | None
    especie: str | None
    carteira: str | None
    data_emissao: date | None
    vencimento: date | None
    valor: Decimal
    beneficiario_nome: str | None
    beneficiario_cnpj: str | None
    situacao: Situacao
    qualidade: Qualidade
    data_pagamento: date | None
    valor_pago: Decimal | None
    divergencias: list[str]
    observacao: str | None
    criado_em: datetime
    atualizado_em: datetime
    deletado_em: datetime | None
    pagador_nome: str | None = None
    pagador_cpf_cnpj: str | None = None

    @computed_field
    @property
    def vencido(self) -> bool:
        return (
            self.situacao == Situacao.aberto
            and self.vencimento is not None
            and self.vencimento < date.today()
        )


class BoletoPatch(BaseModel):
    pagador_id: int | None = None
    nosso_numero: str | None = None
    num_documento: str | None = None
    especie: str | None = None
    carteira: str | None = None
    data_emissao: date | None = None
    vencimento: date | None = None
    valor: Decimal | None = None
    situacao: Situacao | None = None
    observacao: str | None = None


class PagarIn(BaseModel):
    data_pagamento: date
    valor_pago: Decimal


class PaginaBoletos(BaseModel):
    items: list[BoletoOut]
    total: int
    page: int
    size: int
    pages: int


class GrupoPagador(BaseModel):
    """Uma linha por pessoa: os boletos dela ficam sob o nome, não repetidos."""

    pagador_id: int
    nome: str
    cpf_cnpj: str | None
    provisorio: bool
    qtd: int
    total: Decimal
    qtd_aberto: int
    total_aberto: Decimal
    qtd_pago: int
    total_pago: Decimal
    qtd_vencido: int
    total_vencido: Decimal
    qtd_revisao: int
    proximo_vencimento: date | None


class PagarLoteIn(BaseModel):
    ids: list[int]
    data_pagamento: date
    # Sem valor_pago, cada boleto é baixado pelo próprio valor
    valor_pago: Decimal | None = None


class ResultadoLote(BaseModel):
    pagos: int
    ignorados: list[int] = Field(default_factory=list)


# ---------- Upload ----------

class UploadOut(ORMModel):
    id: int
    nome_arquivo: str
    hash_sha256: str
    qtd_paginas: int
    qtd_boletos_novos: int
    qtd_atualizados: int = 0
    qtd_duplicados: int
    qtd_ignoradas: int
    qtd_revisao: int
    reprocessado_de_id: int | None
    criado_em: datetime
    deletado_em: datetime | None


class ResultadoArquivoOut(BaseModel):
    nome: str
    upload_id: int | None = None
    novos: int = 0
    atualizados: int = 0
    duplicados: int = 0
    ignoradas: list[int] = Field(default_factory=list)
    revisao_manual: int = 0
    erro: str | None = None


class RespostaUpload(BaseModel):
    arquivos: list[ResultadoArquivoOut]


# ---------- Auditoria ----------

class AuditoriaOut(ORMModel):
    id: int
    entidade: str
    entidade_id: int
    acao: str
    campo: str | None
    valor_anterior: str | None
    valor_novo: str | None
    origem: str
    autor: str
    criado_em: datetime


# ---------- Dashboard ----------

class PorPagador(BaseModel):
    nome: str
    qtd: int
    valor_unitario: Decimal
    subtotal: Decimal


class PorMes(BaseModel):
    mes: str
    total: Decimal
    qtd: int


class PorSituacao(BaseModel):
    situacao: str
    qtd: int
    total: Decimal


class DashboardOut(BaseModel):
    total_geral: Decimal
    total_aberto: Decimal
    total_pago: Decimal
    total_vencido: Decimal
    qtd_boletos: int
    qtd_pagadores: int
    valor_medio: Decimal
    qtd_revisao_manual: int
    por_pagador: list[PorPagador]
    por_mes: list[PorMes]
    por_situacao: list[PorSituacao]
