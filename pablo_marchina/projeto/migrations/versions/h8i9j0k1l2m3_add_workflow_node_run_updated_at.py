"""add workflow_node_runs updated_at column

The ORM model inherits TimestampMixin, but the original table migration only
created created_at. PostgreSQL therefore failed whenever workflow node records
were selected through the ORM.

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-08-02 21:10:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "h8i9j0k1l2m3"
down_revision: Union[str, None] = "g7h8i9j0k1l2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("workflow_node_runs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
        )

    # TimestampMixin supplies application-side defaults and on-update values.
    # Keep the database default only for direct SQL inserts and old clients.


def downgrade() -> None:
    with op.batch_alter_table("workflow_node_runs", schema=None) as batch_op:
        batch_op.drop_column("updated_at")
