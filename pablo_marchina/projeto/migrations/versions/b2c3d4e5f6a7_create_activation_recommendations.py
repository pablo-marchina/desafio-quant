"""create activation_recommendations

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-12 14:30:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "activation_recommendations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("analysis_run_id", sa.String(length=36), nullable=False),
        sa.Column("playbook_id", sa.String(length=100), nullable=False),
        sa.Column("playbook_name", sa.String(length=255), nullable=False),
        sa.Column("matched_gap_types_json", sa.JSON(), nullable=False),
        sa.Column("matched_claim_ids_json", sa.JSON(), nullable=False),
        sa.Column("nvidia_technologies_json", sa.JSON(), nullable=False),
        sa.Column("technical_experiment", sa.Text(), nullable=False),
        sa.Column("success_metrics_json", sa.JSON(), nullable=False),
        sa.Column("recommended_motion", sa.String(length=50), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.String(length=20), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("evidence_refs_json", sa.JSON(), nullable=False),
        sa.Column("risks_json", sa.JSON(), nullable=False),
        sa.Column("next_step", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("activation_recommendations", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_activation_recommendations_analysis_run_id"),
            ["analysis_run_id"],
            unique=False,
        )
        batch_op.create_index(batch_op.f("ix_activation_recommendations_playbook_id"), ["playbook_id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_activation_recommendations_recommended_motion"),
            ["recommended_motion"],
            unique=False,
        )
        batch_op.create_index(batch_op.f("ix_activation_recommendations_priority"), ["priority"], unique=False)
        batch_op.create_index("ix_activation_run_id", ["analysis_run_id"], unique=False)
        batch_op.create_index("ix_activation_playbook_id", ["playbook_id"], unique=False)
        batch_op.create_index("ix_activation_recommended_motion", ["recommended_motion"], unique=False)
        batch_op.create_index("ix_activation_priority", ["priority"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("activation_recommendations", schema=None) as batch_op:
        batch_op.drop_index("ix_activation_priority")
        batch_op.drop_index("ix_activation_recommended_motion")
        batch_op.drop_index("ix_activation_playbook_id")
        batch_op.drop_index("ix_activation_run_id")
        batch_op.drop_index(batch_op.f("ix_activation_recommendations_priority"))
        batch_op.drop_index(batch_op.f("ix_activation_recommendations_recommended_motion"))
        batch_op.drop_index(batch_op.f("ix_activation_recommendations_playbook_id"))
        batch_op.drop_index(batch_op.f("ix_activation_recommendations_analysis_run_id"))
    op.drop_table("activation_recommendations")
