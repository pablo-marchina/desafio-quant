"""add startup discovery submissions

Revision ID: a4e1c9d8f2b6
Revises: f1a2b3c4d5e6
Create Date: 2026-06-29 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a4e1c9d8f2b6"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "startup_discovery_submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hub_name", sa.String(length=128), nullable=False),
        sa.Column("website_url", sa.Text(), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=True),
        sa.Column("hub_profile_url", sa.Text(), nullable=True),
        sa.Column("short_description", sa.Text(), nullable=True),
        sa.Column("declared_sector", sa.String(length=128), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["startup_discovery_runs.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_startup_discovery_submissions_run_id",
        "startup_discovery_submissions",
        ["run_id"],
    )
    op.create_index(
        "ix_startup_discovery_submissions_job_id",
        "startup_discovery_submissions",
        ["job_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_startup_discovery_submissions_job_id",
        table_name="startup_discovery_submissions",
    )
    op.drop_index(
        "ix_startup_discovery_submissions_run_id",
        table_name="startup_discovery_submissions",
    )
    op.drop_table("startup_discovery_submissions")
