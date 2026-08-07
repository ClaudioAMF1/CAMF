"""arquivo_pdf: PDFs guardados no banco (hospedagem sem disco persistente)

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-07

"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "arquivo_pdf",
        sa.Column("hash_sha256", sa.String(64), primary_key=True),
        sa.Column("conteudo", sa.LargeBinary(), nullable=False),
        sa.Column("tamanho", sa.Integer(), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("arquivo_pdf")
