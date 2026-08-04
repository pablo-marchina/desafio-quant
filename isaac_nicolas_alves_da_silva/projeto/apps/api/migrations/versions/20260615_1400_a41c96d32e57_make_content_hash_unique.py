"""make content hash unique

Revision ID: a41c96d32e57
Revises: f3f7f3959ccc
Create Date: 2026-06-15 14:00:00
"""

from typing import Sequence, Union

from alembic import op


revision: str = "a41c96d32e57"
down_revision: Union[str, None] = "f3f7f3959ccc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Substitui o indice comum por um indice unico para o hash."""

    # Se ja houver hashes repetidos, a criacao falhara em vez de apagar dados.
    op.drop_index(
        op.f("ix_scraping_results_content_hash"),
        table_name="scraping_results",
    )
    op.create_index(
        op.f("ix_scraping_results_content_hash"),
        "scraping_results",
        ["content_hash"],
        unique=True,
    )


def downgrade() -> None:
    """Restaura o indice comum, permitindo hashes repetidos novamente."""

    op.drop_index(
        op.f("ix_scraping_results_content_hash"),
        table_name="scraping_results",
    )
    op.create_index(
        op.f("ix_scraping_results_content_hash"),
        "scraping_results",
        ["content_hash"],
        unique=False,
    )
