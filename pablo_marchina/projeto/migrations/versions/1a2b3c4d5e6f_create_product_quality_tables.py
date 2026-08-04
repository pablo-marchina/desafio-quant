"""create product_quality_tables

Revision ID: 1a2b3c4d5e6f
Revises: c3d4e5f6a7b8
Create Date: 2026-06-12 16:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "1a2b3c4d5e6f"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "product_quality_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("analysis_run_id", sa.String(length=36), nullable=False),
        sa.Column("dossier_id", sa.String(length=36), nullable=True),
        sa.Column("action_brief_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evaluator_version", sa.String(length=50), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("degraded_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["action_brief_id"], ["action_brief_records.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["dossier_id"], ["activation_dossier_records.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("product_quality_runs", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_product_quality_runs_analysis_run_id"), ["analysis_run_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_product_quality_runs_status"), ["status"], unique=False)
        batch_op.create_index(batch_op.f("ix_product_quality_runs_created_at"), ["created_at"], unique=False)
        batch_op.create_index("ix_quality_run_analysis_run_id", ["analysis_run_id"], unique=False)

    op.create_table(
        "product_quality_metrics",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("quality_run_id", sa.String(length=36), nullable=False),
        sa.Column("metric_name", sa.String(length=100), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["quality_run_id"], ["product_quality_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("product_quality_metrics", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_product_quality_metrics_quality_run_id"),
            ["quality_run_id"],
            unique=False,
        )
        batch_op.create_index(batch_op.f("ix_product_quality_metrics_metric_name"), ["metric_name"], unique=False)
        batch_op.create_index(batch_op.f("ix_product_quality_metrics_passed"), ["passed"], unique=False)
        batch_op.create_index(batch_op.f("ix_product_quality_metrics_severity"), ["severity"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("product_quality_metrics", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_product_quality_metrics_severity"))
        batch_op.drop_index(batch_op.f("ix_product_quality_metrics_passed"))
        batch_op.drop_index(batch_op.f("ix_product_quality_metrics_metric_name"))
        batch_op.drop_index(batch_op.f("ix_product_quality_metrics_quality_run_id"))
    op.drop_table("product_quality_metrics")
    with op.batch_alter_table("product_quality_runs", schema=None) as batch_op:
        batch_op.drop_index("ix_quality_run_analysis_run_id")
        batch_op.drop_index(batch_op.f("ix_product_quality_runs_created_at"))
        batch_op.drop_index(batch_op.f("ix_product_quality_runs_status"))
        batch_op.drop_index(batch_op.f("ix_product_quality_runs_analysis_run_id"))
    op.drop_table("product_quality_runs")
