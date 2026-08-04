"""evidence legal_basis: base legal LGPD (F1.13)

Adiciona `evidence.legal_basis` (base legal LGPD da coleta — `LegalBasis`). Preenchida
para evidência de **founder** (legítimo interesse sobre dado profissional público,
Art. 7 IX/§4); NULL para evidência de empresa/score/recomendação. Nullable, sem índice.

Revision ID: c3a2f1b4d5e6
Revises: b7c1f0a9d2e3
Create Date: 2026-06-04 12:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c3a2f1b4d5e6'
down_revision: str | None = 'b7c1f0a9d2e3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('evidence', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('legal_basis', sqlmodel.sql.sqltypes.AutoString(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table('evidence', schema=None) as batch_op:
        batch_op.drop_column('legal_basis')
