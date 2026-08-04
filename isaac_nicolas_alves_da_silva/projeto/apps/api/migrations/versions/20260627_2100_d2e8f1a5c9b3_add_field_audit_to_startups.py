"""add field_confidence and field_evidence_ids to startups

Revision ID: d2e8f1a5c9b3
Revises: c5d9a3e7b2f1
Create Date: 2026-06-27 21:00:00.000000

Startups V4 (slice auditoria): persiste a confianca por campo basico
extraido (founders, sector, description, funding_stage, customers) e os
IDs das evidencias que sustentaram cada campo. Populados pelo
ExtractStartupProfile apos cada rodada de extracao.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d2e8f1a5c9b3"
down_revision = "c5d9a3e7b2f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "startups",
        sa.Column(
            "field_confidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "startups",
        sa.Column(
            "field_evidence_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )


def downgrade() -> None:
    op.drop_column("startups", "field_evidence_ids")
    op.drop_column("startups", "field_confidence")
