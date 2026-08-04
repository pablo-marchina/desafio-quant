<%doc>
Template usado pelo Alembic para criar cada novo arquivo em migrations/versions/.
Toda vez que rodamos `alembic revision`, o Alembic preenche os campos abaixo
(revision, down_revision, etc) e gera um arquivo novo a partir deste molde.
</%doc>"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# Identificador único desta migration.
revision: str = ${repr(up_revision)}

# Migration anterior, na qual esta se baseia. None se for a primeira.
down_revision: Union[str, None] = ${repr(down_revision)}

# Usados quando há ramificações no histórico de migrations (não é o nosso
# caso por enquanto, mas o Alembic exige que estes nomes existam).
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    """Aplica esta migration (avança o schema)."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Desfaz esta migration (volta o schema ao estado anterior)."""
    ${downgrades if downgrades else "pass"}
