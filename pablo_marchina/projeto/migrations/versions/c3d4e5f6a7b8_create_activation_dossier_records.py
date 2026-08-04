"""create activation_dossier_records

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-12 15:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "activation_dossier_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("analysis_run_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("dossier_json", sa.JSON(), nullable=False),
        sa.Column("dossier_markdown", sa.Text(), nullable=False),
        sa.Column("is_latest", sa.Boolean(), nullable=False),
        sa.Column("evidence_coverage", sa.Float(), nullable=False),
        sa.Column("unsupported_claim_count", sa.Integer(), nullable=False),
        sa.Column("top_activation_playbook_id", sa.String(length=100), nullable=True),
        sa.Column("recommended_motion", sa.String(length=50), nullable=False),
        sa.Column("review_status", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("analysis_run_id", "version", name="uq_run_dossier_version"),
    )
    with op.batch_alter_table("activation_dossier_records", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_activation_dossier_records_analysis_run_id"),
            ["analysis_run_id"],
            unique=False,
        )
        batch_op.create_index("ix_dossier_run_latest", ["analysis_run_id", "is_latest"], unique=False)
        batch_op.create_index("ix_dossier_recommended_motion", ["recommended_motion"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("activation_dossier_records", schema=None) as batch_op:
        batch_op.drop_index("ix_dossier_recommended_motion")
        batch_op.drop_index("ix_dossier_run_latest")
        batch_op.drop_index(batch_op.f("ix_activation_dossier_records_analysis_run_id"))
    op.drop_table("activation_dossier_records")
