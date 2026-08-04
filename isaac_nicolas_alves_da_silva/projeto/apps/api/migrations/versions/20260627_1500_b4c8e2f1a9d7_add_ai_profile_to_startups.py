"""add ai_profile to startups

Revision ID: b4c8e2f1a9d7
Revises: a3c7f9e2b4d8
Create Date: 2026-06-27 15:00:00.000000

Briefing V4, passo 2: persiste o StartupAIProfile estruturado extraido pelo
Extraction Agent (workload type, model type, data modality, deployment stage,
infra environment, gpu need, latency requirement, scale signal, current tools,
business goal, field_confidence e field_evidence_ids) como JSONB na startup.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b4c8e2f1a9d7"
down_revision = "a3c7f9e2b4d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "startups",
        sa.Column(
            "ai_profile",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("startups", "ai_profile")
