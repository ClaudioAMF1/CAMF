"""boleto.pagina: página do PDF de origem, para reabrir o boleto

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-05

"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("boleto", sa.Column("pagina", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("boleto", "pagina")
