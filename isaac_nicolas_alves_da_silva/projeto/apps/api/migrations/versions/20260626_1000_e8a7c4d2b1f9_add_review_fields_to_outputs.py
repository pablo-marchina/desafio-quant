"""add review fields to recommendations and briefings

Revision ID: e8a7c4d2b1f9
Revises: d7e3f1a2b9c4
Create Date: 2026-06-26 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "e8a7c4d2b1f9"
down_revision = "d7e3f1a2b9c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table_name in ("recommendations", "briefings"):
        op.add_column(
            table_name,
            sa.Column(
                "review_status",
                sa.String(length=16),
                nullable=False,
                server_default="pending",
            ),
        )
        op.add_column(
            table_name,
            sa.Column("review_comment", sa.Text(), nullable=True),
        )
        op.add_column(
            table_name,
            sa.Column("reviewed_by", sa.String(length=120), nullable=True),
        )
        op.add_column(
            table_name,
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    for table_name in ("briefings", "recommendations"):
        op.drop_column(table_name, "reviewed_at")
        op.drop_column(table_name, "reviewed_by")
        op.drop_column(table_name, "review_comment")
        op.drop_column(table_name, "review_status")
