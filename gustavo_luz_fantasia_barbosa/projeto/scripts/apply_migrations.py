from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.config import get_settings
from app.storage import DatabaseUnavailable, get_connection


MIGRATIONS_DIR = REPO_ROOT / "database" / "migrations"


def applied_versions(cursor) -> set[str]:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    cursor.execute("SELECT version FROM schema_migrations")
    return {row[0] for row in cursor.fetchall()}


def apply_migrations() -> int:
    settings = get_settings()
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_files:
        print(f"Nenhuma migration encontrada em {MIGRATIONS_DIR}.")
        return 0

    with get_connection(settings) as connection:
        with connection.cursor() as cursor:
            already_applied = applied_versions(cursor)
            applied = 0
            for migration in migration_files:
                version = migration.stem
                if version in already_applied:
                    continue
                cursor.execute(migration.read_text(encoding="utf-8"))
                cursor.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s)",
                    (version,),
                )
                applied += 1
                print(f"Applied migration: {version}")
    return applied


if __name__ == "__main__":
    try:
        count = apply_migrations()
    except DatabaseUnavailable as error:
        raise SystemExit(str(error)) from error
    print(f"Migrations aplicadas: {count}")
