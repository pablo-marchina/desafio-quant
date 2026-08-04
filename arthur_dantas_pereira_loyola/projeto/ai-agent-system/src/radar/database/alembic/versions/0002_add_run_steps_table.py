"""add run_steps table for pipeline progress tracking

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-23
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS run_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL REFERENCES runs(id),
            step_key TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'idle',
            detail TEXT,
            error_message TEXT,
            started_at TEXT,
            completed_at TEXT
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_run_steps_run_id ON run_steps(run_id)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_run_steps_run_step ON run_steps(run_id, step_key)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_run_steps_run_id")
    op.execute("DROP TABLE IF EXISTS run_steps")

