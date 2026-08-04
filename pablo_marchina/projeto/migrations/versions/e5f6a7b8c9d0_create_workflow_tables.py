"""create workflow tables (WorkflowRun + WorkflowNodeRun)

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-13 18:40:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "startup_id",
            sa.String(36),
            sa.ForeignKey("startups.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "discovery_candidate_id",
            sa.String(36),
            sa.ForeignKey("startup_discovery_candidates.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "analysis_run_id",
            sa.String(36),
            sa.ForeignKey("analysis_runs.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("status", sa.String(50), nullable=False, server_default="queued", index=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_node", sa.String(100), nullable=False, server_default=""),
        sa.Column("graph_version", sa.String(50), nullable=False, server_default="1.0"),
        sa.Column("state_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("degraded_reason", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            index=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_workflow_run_startup", "workflow_runs", ["startup_id"])
    op.create_index("ix_workflow_run_analysis_run", "workflow_runs", ["analysis_run_id"])
    op.create_index("ix_workflow_run_status", "workflow_runs", ["status"])
    op.create_index("ix_workflow_run_current_node", "workflow_runs", ["current_node"])
    op.create_index("ix_workflow_run_graph_version", "workflow_runs", ["graph_version"])

    op.create_table(
        "workflow_node_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "workflow_run_id",
            sa.String(36),
            sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("node_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input_snapshot_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("output_snapshot_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("metadata_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_workflow_node_run_workflow_node", "workflow_node_runs", ["workflow_run_id", "node_name"])
    op.create_index("ix_workflow_node_run_status", "workflow_node_runs", ["status"])
    op.create_index("ix_workflow_node_run_retry", "workflow_node_runs", ["retry_count"])


def downgrade() -> None:
    op.drop_table("workflow_node_runs")
    op.drop_table("workflow_runs")
