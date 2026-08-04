"""evidence source_policy: politica de ToS por fonte (F1.15)

Adiciona `evidence.source_policy` ('<fonte>:<policy>', ex.: 'brazil-journal:allow' ou
'unlisted:allow') — registra, por evidencia, sob qual decisao de ToS (allowlist/denylist
das seeds) a fonte foi coletada. Estende a anotacao de proveniencia (F1.8/F1.13).
Nullable, sem indice.

Revision ID: d4b3a2c1e0f5
Revises: c3a2f1b4d5e6
Create Date: 2026-06-04 13:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd4b3a2c1e0f5'
down_revision: str | None = 'c3a2f1b4d5e6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('evidence', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('source_policy', sqlmodel.sql.sqltypes.AutoString(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table('evidence', schema=None) as batch_op:
        batch_op.drop_column('source_policy')
