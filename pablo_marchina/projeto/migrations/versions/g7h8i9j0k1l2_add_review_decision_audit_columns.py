"""add review_decision audit columns

Adds startup_id, thread_id, review_payload_snapshot,
status_before_resume and status_after_resume to the
review_decisions table.

Revision ID: g7h8i9j0k1l2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-17 01:04:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "g7h8i9j0k1l2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("review_decisions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "startup_id",
                sa.String(length=36),
                nullable=False,
                server_default="",
            )
        )
        batch_op.add_column(
            sa.Column(
                "thread_id",
                sa.String(length=255),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "review_payload_snapshot",
                sa.JSON(),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "status_before_resume",
                sa.String(length=50),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "status_after_resume",
                sa.String(length=50),
                nullable=True,
            )
        )
        batch_op.create_index(
            batch_op.f("ix_review_decisions_startup_id"),
            ["startup_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_review_decisions_thread_id"),
            ["thread_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            "fk_review_decisions_startup_id_startups",
            "startups",
            ["startup_id"],
            ["id"],
            ondelete="CASCADE",
        )

    # Remove the server_default now that the column exists
    with op.batch_alter_table("review_decisions", schema=None) as batch_op:
        batch_op.alter_column(
            "startup_id",
            server_default=None,
        )


def downgrade() -> None:
    with op.batch_alter_table("review_decisions", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_review_decisions_startup_id_startups",
            type_="foreignkey",
        )
        batch_op.drop_index(
            batch_op.f("ix_review_decisions_thread_id"),
        )
        batch_op.drop_index(
            batch_op.f("ix_review_decisions_startup_id"),
        )
        batch_op.drop_column("status_after_resume")
        batch_op.drop_column("status_before_resume")
        batch_op.drop_column("review_payload_snapshot")
        batch_op.drop_column("thread_id")
        batch_op.drop_column("startup_id")
