from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

from scripts.apply_supabase_migration import _normalize_database_url


POSTGRES_IMAGE = "postgres:17-alpine"


def create_backup(database_url: str, output_dir: Path) -> tuple[Path, Path]:
    connection = _connection_parts(database_url)
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    filename = f"nvidia_inception_{timestamp}.dump"
    command = [
        "docker",
        "run",
        "--rm",
        "-e",
        "PGPASSWORD",
        "-v",
        f"{output_dir}:/backups",
        POSTGRES_IMAGE,
        "pg_dump",
        "--host",
        str(connection["host"]),
        "--port",
        str(connection["port"]),
        "--username",
        str(connection["username"]),
        "--dbname",
        str(connection["database"]),
        "--schema",
        "nvidia_inception",
        "--format=custom",
        "--no-owner",
        "--no-privileges",
        "--file",
        f"/backups/{filename}",
    ]
    _run(command, str(connection["password"]))
    backup_path = output_dir / filename
    manifest_path = backup_path.with_suffix(".manifest.json")
    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "filename": filename,
        "format": "pg_dump_custom",
        "schema": "nvidia_inception",
        "sha256": _sha256(backup_path),
        "size_bytes": backup_path.stat().st_size,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return backup_path, manifest_path


def restore_backup(
    backup_path: Path,
    target_database_url: str,
    source_database_url: str,
) -> None:
    _assert_isolated_target(source_database_url, target_database_url)
    target = _connection_parts(target_database_url)
    backup_path = backup_path.resolve()
    if not backup_path.is_file():
        raise FileNotFoundError(backup_path)
    _bootstrap_restore_target(target)
    command = [
        "docker",
        "run",
        "--rm",
        "-e",
        "PGPASSWORD",
        "-v",
        f"{backup_path.parent}:/backups:ro",
        POSTGRES_IMAGE,
        "pg_restore",
        "--host",
        str(target["host"]),
        "--port",
        str(target["port"]),
        "--username",
        str(target["username"]),
        "--dbname",
        str(target["database"]),
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-privileges",
        f"/backups/{backup_path.name}",
    ]
    _run(command, str(target["password"]))


def _bootstrap_restore_target(target: dict[str, str | int]) -> None:
    sql = """
    do $$
    begin
      if not exists (select 1 from pg_roles where rolname = 'service_role') then
        create role service_role;
      end if;
      if not exists (select 1 from pg_roles where rolname = 'anon') then
        create role anon;
      end if;
      if not exists (select 1 from pg_roles where rolname = 'authenticated') then
        create role authenticated;
      end if;
    end $$;
    create schema if not exists auth;
    create or replace function auth.role()
    returns text language sql stable
    as $$ select coalesce(nullif(current_setting('request.jwt.claim.role', true), ''), current_user::text) $$;
    create extension if not exists pgcrypto;
    """
    command = [
        "docker",
        "run",
        "--rm",
        "-e",
        "PGPASSWORD",
        POSTGRES_IMAGE,
        "psql",
        "--host",
        str(target["host"]),
        "--port",
        str(target["port"]),
        "--username",
        str(target["username"]),
        "--dbname",
        str(target["database"]),
        "--set",
        "ON_ERROR_STOP=1",
        "--command",
        sql,
    ]
    _run(command, str(target["password"]))


def verify_manifest(backup_path: Path, manifest_path: Path) -> bool:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return manifest.get("sha256") == _sha256(backup_path)


def _assert_isolated_target(source_url: str, target_url: str) -> None:
    source = _connection_parts(source_url)
    target = _connection_parts(target_url)
    source_identity = (source["host"], source["port"], source["database"])
    target_identity = (target["host"], target["port"], target["database"])
    if source_identity == target_identity:
        raise ValueError("Restauracao recusada: o destino coincide com o banco de origem")


def _connection_parts(database_url: str) -> dict[str, str | int]:
    parsed = urlsplit(_normalize_database_url(database_url))
    if not parsed.hostname or not parsed.username or parsed.password is None:
        raise ValueError("DATABASE_URL invalida")
    return {
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "username": unquote(parsed.username),
        "password": unquote(parsed.password),
        "database": parsed.path.lstrip("/") or "postgres",
    }


def _run(command: list[str], password: str) -> None:
    environment = {**os.environ, "PGPASSWORD": password}
    subprocess.run(command, check=True, env=environment)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
