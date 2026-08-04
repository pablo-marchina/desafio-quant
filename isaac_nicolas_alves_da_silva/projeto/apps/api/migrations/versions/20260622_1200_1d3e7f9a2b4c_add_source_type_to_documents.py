"""add source_type to documents

Revision ID: 1d3e7f9a2b4c
Revises: f77998c46d08
Create Date: 2026-06-22 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "1d3e7f9a2b4c"
down_revision: str | None = "f77998c46d08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "source_type",
            sa.String(length=64),
            server_default="startup_evidence",
            nullable=False,
        ),
    )
    op.create_index(
        "ix_documents_source_type",
        "documents",
        ["source_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_documents_source_type", table_name="documents")
    op.drop_column("documents", "source_type")
