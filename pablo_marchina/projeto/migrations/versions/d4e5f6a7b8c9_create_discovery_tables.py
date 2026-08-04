"""create discovery_tables (DiscoveryRun + StartupDiscoveryCandidate)

Revision ID: d4e5f6a7b8c9
Revises: 1a2b3c4d5e6f
Create Date: 2026-06-13 18:20:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "1a2b3c4d5e6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "discovery_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_id", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("query_json", sa.JSON(), nullable=False),
        sa.Column("results_count", sa.Integer(), nullable=False),
        sa.Column("candidates_created", sa.Integer(), nullable=False),
        sa.Column("duplicates_found", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("discovery_runs", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_discovery_runs_source_id"), ["source_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_discovery_runs_status"), ["status"], unique=False)

    op.create_table(
        "startup_discovery_candidates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("discovery_run_id", sa.String(length=36), nullable=True),
        sa.Column("source_id", sa.String(length=100), nullable=False),
        sa.Column("discovered_name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("website", sa.String(length=2048), nullable=False),
        sa.Column("country", sa.String(length=100), nullable=False),
        sa.Column("sector", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("raw_text_excerpt", sa.Text(), nullable=False),
        sa.Column("ai_native_signals_json", sa.JSON(), nullable=False),
        sa.Column("evidence_refs_json", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("promoted_startup_id", sa.String(length=36), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["discovery_run_id"], ["discovery_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["promoted_startup_id"], ["startups.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("startup_discovery_candidates", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_startup_discovery_candidates_source_id"), ["source_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_startup_discovery_candidates_status"), ["status"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_startup_discovery_candidates_normalized_name"),
            ["normalized_name"],
            unique=False,
        )
        batch_op.create_index(batch_op.f("ix_startup_discovery_candidates_website"), ["website"], unique=False)
        batch_op.create_index(batch_op.f("ix_startup_discovery_candidates_confidence"), ["confidence"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_startup_discovery_candidates_discovery_run_id"),
            ["discovery_run_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("startup_discovery_candidates", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_startup_discovery_candidates_discovery_run_id"))
        batch_op.drop_index(batch_op.f("ix_startup_discovery_candidates_confidence"))
        batch_op.drop_index(batch_op.f("ix_startup_discovery_candidates_website"))
        batch_op.drop_index(batch_op.f("ix_startup_discovery_candidates_normalized_name"))
        batch_op.drop_index(batch_op.f("ix_startup_discovery_candidates_status"))
        batch_op.drop_index(batch_op.f("ix_startup_discovery_candidates_source_id"))
    op.drop_table("startup_discovery_candidates")
    with op.batch_alter_table("discovery_runs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_discovery_runs_status"))
        batch_op.drop_index(batch_op.f("ix_discovery_runs_source_id"))
    op.drop_table("discovery_runs")
