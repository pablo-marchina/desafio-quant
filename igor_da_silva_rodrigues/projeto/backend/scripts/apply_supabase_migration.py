import os
import sys
from pathlib import Path
from urllib.parse import quote, unquote

import psycopg
from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")


def _normalize_database_url(database_url: str) -> str:
    scheme, remainder = database_url.split("://", 1)
    credentials, host = remainder.rsplit("@", 1)
    username, password = credentials.split(":", 1)
    encoded_username = quote(unquote(username), safe=".")
    encoded_password = quote(unquote(password), safe="")
    return f"{scheme}://{encoded_username}:{encoded_password}@{host}"


if __name__ == "__main__":
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL não configurada em backend/.env")

    database_url = _normalize_database_url(database_url)
    migration_path = BACKEND_DIR / "app" / "persistence" / "migration.sql"
    migration_sql = migration_path.read_text(encoding="utf-8")

    try:
        with psycopg.connect(database_url, connect_timeout=15) as connection:
            with connection.cursor() as cursor:
                cursor.execute(migration_sql)
        print("Migration nvidia_inception aplicada com sucesso.")
    except psycopg.Error as exc:
        print(f"Falha ao aplicar migration: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
