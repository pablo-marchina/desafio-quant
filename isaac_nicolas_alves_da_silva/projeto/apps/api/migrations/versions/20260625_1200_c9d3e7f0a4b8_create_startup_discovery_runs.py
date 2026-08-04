"""Cria tabela startup_discovery_runs para o modulo de descoberta automatica de startups.

Revision ID: c9d3e7f0a4b8
Revises: b3f6e91c7d45
Create Date: 2026-06-25 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c9d3e7f0a4b8"
down_revision: str | None = "b3f6e91c7d45"
branch_labels: str | Sequence[str] | None = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "startup_discovery_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("hubs_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("urls_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("jobs_submitted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_startup_discovery_runs_created_at",
        "startup_discovery_runs",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_startup_discovery_runs_created_at", "startup_discovery_runs")
    op.drop_table("startup_discovery_runs")
