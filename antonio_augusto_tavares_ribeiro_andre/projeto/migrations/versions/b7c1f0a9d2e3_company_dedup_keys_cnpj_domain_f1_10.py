"""company dedup keys: cnpj + domain (F1.10)

Adiciona as chaves de dedup do cohort builder (F1.10/F1.14): `company.domain` (host
normalizado do website) e `company.cnpj` (registro BR). Índices únicos — NULLs distintos
em SQLite/Postgres, então empresas sem a chave não colidem.

Revision ID: b7c1f0a9d2e3
Revises: 5d50b03281c3
Create Date: 2026-06-04 02:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'b7c1f0a9d2e3'
down_revision: Union[str, None] = '5d50b03281c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('company', schema=None) as batch_op:
        batch_op.add_column(sa.Column('domain', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.add_column(sa.Column('cnpj', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.create_index(batch_op.f('ix_company_domain'), ['domain'], unique=True)
        batch_op.create_index(batch_op.f('ix_company_cnpj'), ['cnpj'], unique=True)


def downgrade() -> None:
    with op.batch_alter_table('company', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_company_cnpj'))
        batch_op.drop_index(batch_op.f('ix_company_domain'))
        batch_op.drop_column('cnpj')
        batch_op.drop_column('domain')
