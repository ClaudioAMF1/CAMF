"""Esquema inicial: pagador, upload, boleto, auditoria

Revision ID: 0001
Revises:
Create Date: 2026-07-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

situacao_enum = sa.Enum("aberto", "pago", "cancelado", name="situacao_enum")
qualidade_enum = sa.Enum("ok", "revisao_manual", name="qualidade_enum")


def upgrade() -> None:
    op.create_table(
        "pagador",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cpf_cnpj", sa.String(14), nullable=True, unique=True),
        sa.Column("nome", sa.String(255), nullable=False),
        sa.Column("nome_normalizado", sa.String(255), nullable=False),
        sa.Column("endereco", sa.String(255)),
        sa.Column("bairro", sa.String(120)),
        sa.Column("municipio", sa.String(120)),
        sa.Column("uf", sa.String(2)),
        sa.Column("cep", sa.String(8)),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deletado_em", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_pagador_nome_normalizado", "pagador", ["nome_normalizado"])
    op.create_index("ix_pagador_deletado_em", "pagador", ["deletado_em"])

    op.create_table(
        "upload",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome_arquivo", sa.String(255), nullable=False),
        sa.Column("hash_sha256", sa.String(64), nullable=False),
        sa.Column("qtd_paginas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("qtd_boletos_novos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("qtd_duplicados", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("qtd_ignoradas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("qtd_revisao", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reprocessado_de_id", sa.Integer(), sa.ForeignKey("upload.id"), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deletado_em", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_upload_hash_sha256", "upload", ["hash_sha256"])
    op.create_index("ix_upload_deletado_em", "upload", ["deletado_em"])

    op.create_table(
        "boleto",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("upload_id", sa.Integer(), sa.ForeignKey("upload.id"), nullable=False),
        sa.Column("pagador_id", sa.Integer(), sa.ForeignKey("pagador.id"), nullable=False),
        sa.Column("linha_digitavel", sa.String(47), nullable=False, unique=True),
        sa.Column("codigo_barras", sa.String(44), nullable=False),
        sa.Column("nosso_numero", sa.String(30)),
        sa.Column("num_documento", sa.String(30)),
        sa.Column("especie", sa.String(10)),
        sa.Column("carteira", sa.String(10)),
        sa.Column("data_emissao", sa.Date()),
        sa.Column("vencimento", sa.Date()),
        sa.Column("valor", sa.Numeric(12, 2), nullable=False),
        sa.Column("beneficiario_nome", sa.String(255)),
        sa.Column("beneficiario_cnpj", sa.String(14)),
        sa.Column("situacao", situacao_enum, nullable=False, server_default="aberto"),
        sa.Column("qualidade", qualidade_enum, nullable=False, server_default="ok"),
        sa.Column("data_pagamento", sa.Date(), nullable=True),
        sa.Column("valor_pago", sa.Numeric(12, 2), nullable=True),
        sa.Column("divergencias", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("observacao", sa.Text()),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deletado_em", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_boleto_vencimento", "boleto", ["vencimento"])
    op.create_index("ix_boleto_pagador_id", "boleto", ["pagador_id"])
    op.create_index("ix_boleto_situacao", "boleto", ["situacao"])
    op.create_index("ix_boleto_qualidade", "boleto", ["qualidade"])
    op.create_index("ix_boleto_deletado_em", "boleto", ["deletado_em"])

    op.create_table(
        "auditoria",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entidade", sa.String(20), nullable=False),
        sa.Column("entidade_id", sa.Integer(), nullable=False),
        sa.Column("acao", sa.String(30), nullable=False),
        sa.Column("campo", sa.String(60)),
        sa.Column("valor_anterior", sa.Text()),
        sa.Column("valor_novo", sa.Text()),
        sa.Column("origem", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("autor", sa.String(120), nullable=False, server_default="sistema"),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_auditoria_entidade", "auditoria", ["entidade", "entidade_id"])


def downgrade() -> None:
    op.drop_table("auditoria")
    op.drop_table("boleto")
    op.drop_table("upload")
    op.drop_table("pagador")
    situacao_enum.drop(op.get_bind(), checkfirst=True)
    qualidade_enum.drop(op.get_bind(), checkfirst=True)
