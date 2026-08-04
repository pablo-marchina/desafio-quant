"""create claim_records

Revision ID: a1b2c3d4e5f6
Revises: e0d3e59b52e5
Create Date: 2026-06-12 14:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "e0d3e59b52e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "claim_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("startup_id", sa.String(length=36), nullable=False),
        sa.Column("analysis_run_id", sa.String(length=36), nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("claim_type", sa.String(length=50), nullable=False),
        sa.Column("support_level", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.String(length=20), nullable=False),
        sa.Column("evidence_refs_json", sa.JSON(), nullable=False),
        sa.Column("used_in_score", sa.Boolean(), nullable=False),
        sa.Column("used_in_gap", sa.Boolean(), nullable=False),
        sa.Column("used_in_mapping", sa.Boolean(), nullable=False),
        sa.Column("used_in_brief", sa.Boolean(), nullable=False),
        sa.Column("review_status", sa.String(length=20), nullable=False),
        sa.Column("reviewer_notes", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["startup_id"], ["startups.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("claim_records", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_claim_records_analysis_run_id"), ["analysis_run_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_claim_records_claim_type"), ["claim_type"], unique=False)
        batch_op.create_index(batch_op.f("ix_claim_records_created_at"), ["created_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_claim_records_startup_id"), ["startup_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_claim_records_support_level"), ["support_level"], unique=False)
        batch_op.create_index("ix_claim_run_review", ["analysis_run_id", "review_status"], unique=False)
        batch_op.create_index("ix_claim_startup_type", ["startup_id", "claim_type"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("claim_records", schema=None) as batch_op:
        batch_op.drop_index("ix_claim_startup_type")
        batch_op.drop_index("ix_claim_run_review")
        batch_op.drop_index(batch_op.f("ix_claim_records_support_level"))
        batch_op.drop_index(batch_op.f("ix_claim_records_startup_id"))
        batch_op.drop_index(batch_op.f("ix_claim_records_created_at"))
        batch_op.drop_index(batch_op.f("ix_claim_records_claim_type"))
        batch_op.drop_index(batch_op.f("ix_claim_records_analysis_run_id"))
    op.drop_table("claim_records")
