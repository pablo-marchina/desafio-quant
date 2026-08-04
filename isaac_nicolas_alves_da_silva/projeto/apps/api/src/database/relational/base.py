"""Base declarativa compartilhada por todos os models SQLAlchemy."""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


# A convenção gera nomes previsíveis para constraints e índices.
#
# Isso é importante para o Alembic: sem nomes estáveis, migrations futuras
# podem ter dificuldade para alterar ou remover constraints existentes.
naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Classe-base que todos os models relacionais devem herdar."""

    metadata = MetaData(naming_convention=naming_convention)
