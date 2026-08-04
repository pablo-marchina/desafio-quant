"""Conexão com o PostgreSQL (a "ponte" entre o código e o banco).

Lê a DATABASE_URL do .env, cria o "engine" (o motor de conexão) e uma fábrica
de sessões. Uma SESSÃO é o objeto que usamos para conversar com o banco:
inserir, consultar, atualizar, etc.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from db.models import Base

# Carrega as variáveis do arquivo .env para dentro do ambiente do programa.
load_dotenv()


def _normalize(url: str) -> str:
    """Garante que a URL use o driver psycopg 3 (o que instalamos).

    Ao ver "postgresql://", a SQLAlchemy tentaria o driver antigo (psycopg2),
    que não temos. Trocamos para "postgresql+psycopg://" para usar o psycopg 3.
    Assim o seu .env pode continuar com a URL no formato padrão.
    """
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


# Lê a string de conexão do .env. Se faltar, avisamos com clareza.
_raw_url = os.getenv("DATABASE_URL")
if not _raw_url:
    raise RuntimeError("DATABASE_URL não definida no .env")

DATABASE_URL = _normalize(_raw_url)

# O "engine" é o motor que gerencia as conexões com o banco.
engine = create_engine(DATABASE_URL)

# Fábrica de sessões: chamamos SessionLocal() para abrir uma "conversa" nova
# com o banco sempre que precisarmos.
SessionLocal = sessionmaker(bind=engine, class_=Session)


def init_db() -> None:
    """Cria no banco todas as tabelas que ainda não existem.

    Olha todos os modelos que herdam de Base e cria as tabelas
    correspondentes. Se a tabela já existe, não faz nada (não apaga dados).
    """
    Base.metadata.create_all(engine)
