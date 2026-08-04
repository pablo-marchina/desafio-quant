"""add content_hash to documents

Revision ID: e3f7b2a1c9d8
Revises: d2e8f1a5c9b3
Create Date: 2026-06-28 10:00:00.000000

SHA-256 hex do clean_text de cada Document. Nullable para documentos
criados antes desta migracao (valores historicos nao sao backfillados).
Novos documentos sempre recebem o hash; find_by_content_hash so casa
registros nao-nulos, portanto documentos antigos nunca sao reutilizados
indevidamente.
"""

from alembic import op
import sqlalchemy as sa

revision = "e3f7b2a1c9d8"
down_revision = "d2e8f1a5c9b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("content_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_documents_content_hash",
        "documents",
        ["content_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_documents_content_hash", table_name="documents")
    op.drop_column("documents", "content_hash")
