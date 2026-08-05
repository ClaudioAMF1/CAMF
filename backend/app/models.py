import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base, SoftDeleteMixin

JsonList = JSON().with_variant(JSONB(), "postgresql")


class Situacao(str, enum.Enum):
    aberto = "aberto"
    pago = "pago"
    cancelado = "cancelado"


class Qualidade(str, enum.Enum):
    ok = "ok"
    revisao_manual = "revisao_manual"


class TimestampMixin:
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Pagador(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "pagador"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # NULL = pagador provisório (CPF/CNPJ ausente ou inválido na extração)
    cpf_cnpj: Mapped[str | None] = mapped_column(String(14), unique=True, nullable=True)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    nome_normalizado: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    endereco: Mapped[str | None] = mapped_column(String(255))
    bairro: Mapped[str | None] = mapped_column(String(120))
    municipio: Mapped[str | None] = mapped_column(String(120))
    uf: Mapped[str | None] = mapped_column(String(2))
    cep: Mapped[str | None] = mapped_column(String(8))

    boletos: Mapped[list["Boleto"]] = relationship(back_populates="pagador")

    @property
    def provisorio(self) -> bool:
        return self.cpf_cnpj is None


class Upload(Base, SoftDeleteMixin):
    __tablename__ = "upload"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome_arquivo: Mapped[str] = mapped_column(String(255), nullable=False)
    # Índice não-único: reprocessamento com ?forcar=true cria um novo registro
    # com o mesmo hash apontando para o original via reprocessado_de_id.
    hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    qtd_paginas: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    qtd_boletos_novos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Boletos já existentes re-extraídos num reprocessamento (forcar=true)
    qtd_atualizados: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    qtd_duplicados: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    qtd_ignoradas: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    qtd_revisao: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reprocessado_de_id: Mapped[int | None] = mapped_column(
        ForeignKey("upload.id"), nullable=True
    )
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    boletos: Mapped[list["Boleto"]] = relationship(back_populates="upload")


class Boleto(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "boleto"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    upload_id: Mapped[int] = mapped_column(ForeignKey("upload.id"), nullable=False)
    pagador_id: Mapped[int] = mapped_column(
        ForeignKey("pagador.id"), nullable=False, index=True
    )
    linha_digitavel: Mapped[str] = mapped_column(
        String(47), unique=True, nullable=False
    )
    codigo_barras: Mapped[str] = mapped_column(String(44), nullable=False)
    # Página do PDF de origem, para reabrir só o boleto (1-indexado)
    pagina: Mapped[int | None] = mapped_column(Integer)
    nosso_numero: Mapped[str | None] = mapped_column(String(30))
    num_documento: Mapped[str | None] = mapped_column(String(30))
    especie: Mapped[str | None] = mapped_column(String(10))
    carteira: Mapped[str | None] = mapped_column(String(10))
    data_emissao: Mapped[date | None] = mapped_column(Date)
    vencimento: Mapped[date | None] = mapped_column(Date, index=True)
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    beneficiario_nome: Mapped[str | None] = mapped_column(String(255))
    beneficiario_cnpj: Mapped[str | None] = mapped_column(String(14))
    situacao: Mapped[Situacao] = mapped_column(
        Enum(Situacao, name="situacao_enum", values_callable=lambda e: [x.value for x in e]),
        default=Situacao.aberto,
        nullable=False,
        index=True,
    )
    qualidade: Mapped[Qualidade] = mapped_column(
        Enum(Qualidade, name="qualidade_enum", values_callable=lambda e: [x.value for x in e]),
        default=Qualidade.ok,
        nullable=False,
        index=True,
    )
    data_pagamento: Mapped[date | None] = mapped_column(Date)
    valor_pago: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    divergencias: Mapped[list] = mapped_column(JsonList, default=list, nullable=False)
    observacao: Mapped[str | None] = mapped_column(Text)

    upload: Mapped[Upload] = relationship(back_populates="boletos")
    pagador: Mapped[Pagador] = relationship(back_populates="boletos")

    @property
    def vencido(self) -> bool:
        """Derivado, nunca persistido: aberto e com vencimento no passado."""
        return (
            self.situacao == Situacao.aberto
            and self.vencimento is not None
            and self.vencimento < date.today()
        )


class Auditoria(Base):
    """Trilha de auditoria append-only: sem UPDATE, sem DELETE."""

    __tablename__ = "auditoria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entidade: Mapped[str] = mapped_column(String(20), nullable=False)
    entidade_id: Mapped[int] = mapped_column(Integer, nullable=False)
    acao: Mapped[str] = mapped_column(String(30), nullable=False)
    campo: Mapped[str | None] = mapped_column(String(60))
    valor_anterior: Mapped[str | None] = mapped_column(Text)
    valor_novo: Mapped[str | None] = mapped_column(Text)
    origem: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    autor: Mapped[str] = mapped_column(String(120), nullable=False, default="sistema")
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_auditoria_entidade", "entidade", "entidade_id"),)
