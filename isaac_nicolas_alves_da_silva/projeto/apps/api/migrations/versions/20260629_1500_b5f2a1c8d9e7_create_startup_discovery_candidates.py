"""create startup_discovery_candidates and add enrichment fields to runs

Revision ID: b5f2a1c8d9e7
Revises: a4e1c9d8f2b6
Create Date: 2026-06-29 15:00:00.000000

Cria a tabela startup_discovery_candidates para candidatos descobertos
por nome em hubs mode="name" (ex: 100 Open Startups via arquivo JS).

Tambem adiciona dois campos de telemetria em startup_discovery_runs:
  - candidates_discovered: quantos nomes foram extraidos dos hubs
  - candidates_enriched:   quantos tiveram URL oficial encontrada via Tavily
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b5f2a1c8d9e7"
down_revision: str | None = "a4e1c9d8f2b6"
branch_labels: str | Sequence[str] | None = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "startup_discovery_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("normalized_name", sa.String(256), nullable=False),
        sa.Column("discovery_source", sa.String(128), nullable=False),
        sa.Column("discovery_source_url", sa.Text(), nullable=False),
        sa.Column("category", sa.String(128), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("official_website_url", sa.Text(), nullable=True),
        sa.Column("official_site_confidence", sa.Float(), nullable=True),
        sa.Column(
            "enrichment_sources",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="discovered"),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column(
            "url_ingestion_job_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_startup_discovery_candidates_run_id",
        "startup_discovery_candidates",
        ["run_id"],
    )
    op.create_index(
        "ix_startup_discovery_candidates_status",
        "startup_discovery_candidates",
        ["status"],
    )

    op.add_column(
        "startup_discovery_runs",
        sa.Column(
            "candidates_discovered", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "startup_discovery_runs",
        sa.Column(
            "candidates_enriched", sa.Integer(), nullable=False, server_default="0"
        ),
    )


def downgrade() -> None:
    op.drop_column("startup_discovery_runs", "candidates_enriched")
    op.drop_column("startup_discovery_runs", "candidates_discovered")
    op.drop_index(
        "ix_startup_discovery_candidates_status",
        table_name="startup_discovery_candidates",
    )
    op.drop_index(
        "ix_startup_discovery_candidates_run_id",
        table_name="startup_discovery_candidates",
    )
    op.drop_table("startup_discovery_candidates")
