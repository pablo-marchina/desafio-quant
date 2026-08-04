"""Cria as tabelas no PostgreSQL (Bloco 1 — sub-passo 2).

Roda uma vez para preparar o banco. É seguro rodar de novo: tabelas que já
existem não são recriadas nem apagadas.

Uso:
    uv run python scripts/init_db.py
"""

from __future__ import annotations

import sys

from sqlalchemy import inspect

from db.session import engine, init_db


def main() -> int:
    print("Criando tabelas (se ainda não existirem)...")
    init_db()

    # "inspect" pergunta ao banco quais tabelas existem agora — só para
    # confirmarmos visualmente que a criação funcionou.
    tabelas = inspect(engine).get_table_names()
    print(f"[OK] Tabelas no banco: {tabelas}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
