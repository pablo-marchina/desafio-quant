#!/usr/bin/env python3
# ruff: noqa: E402,I001
from __future__ import annotations

import argparse
import configparser
import importlib.util
import json
import os
import socket
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import urlopen

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.load_product_env import load_product_env
from src.governance.artifacts import DEFAULT_EVIDENCE_DIR, write_json

DEFAULT_POSTGRES_URL = "postgresql://postgres:postgres@localhost:5432/startup_radar"
DEFAULT_QDRANT_URL = "http://localhost:6333"
DEFAULT_QDRANT_COLLECTION = "nvidia_corpus"
DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
DEFAULT_TIMEOUT_SECONDS = 5

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"
BLOCKED = "BLOCKED_BY_ENVIRONMENT"


def make_check(
    *,
    check_id: str,
    component: str,
    status: str,
    details: dict[str, Any] | None = None,
    errors: list[str] | None = None,
    remediation: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "component": component,
        "status": status,
        "details": details or {},
        "errors": errors or [],
        "remediation": remediation or [],
    }


def run_doctor(
    *,
    evidence_dir: Path = DEFAULT_EVIDENCE_DIR,
    database_url: str = DEFAULT_POSTGRES_URL,
    qdrant_url: str = DEFAULT_QDRANT_URL,
    qdrant_collection: str = DEFAULT_QDRANT_COLLECTION,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    require_docker_compose: bool = False,
    external_services_ok: bool = True,
) -> dict[str, Any]:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    checks = [
        check_python_version(),
        check_node_version(timeout_seconds=timeout_seconds),
        check_frontend_package_manager(),
        check_import_available("langgraph_import", "LangGraph", "langgraph", "pip install -e .[agents]"),
        check_import_available(
            "qdrant_client_import",
            "Qdrant client",
            "qdrant_client",
            "pip install -e .[rag]",
        ),
        check_import_available(
            "postgres_driver_import",
            "PostgreSQL driver",
            "psycopg2",
            "pip install -e .[postgres]",
        ),
        check_playwright_browsers(),
        check_docker_config(),
        check_docker_cli(timeout_seconds=timeout_seconds),
        check_docker_compose(timeout_seconds=timeout_seconds),
        check_env_configuration(
            database_url=database_url,
            qdrant_url=qdrant_url,
            qdrant_collection=qdrant_collection,
            embedding_model=embedding_model,
        ),
        check_tcp_port("postgres_port", "PostgreSQL TCP port", *_postgres_host_port(database_url)),
        check_postgres_connection(database_url, timeout_seconds=timeout_seconds),
        check_tcp_port("qdrant_port", "Qdrant HTTP port", *_qdrant_host_port(qdrant_url)),
        check_qdrant_service(qdrant_url, timeout_seconds=timeout_seconds),
        check_qdrant_collection(qdrant_url, qdrant_collection, timeout_seconds=timeout_seconds),
        check_alembic_configuration(),
        check_nvidia_corpus(),
        check_embedding_provider(embedding_model),
    ]
    route = resolve_service_route(
        checks,
        require_docker_compose=require_docker_compose,
        external_services_ok=external_services_ok,
    )
    status = aggregate_doctor_status(
        checks,
        require_docker_compose=require_docker_compose,
        external_services_ok=external_services_ok,
    )
    payload = {
        "report_id": "local_proof_doctor_report",
        "status": status,
        "generated_at": datetime.now(UTC).isoformat(),
        "effective_service_route": route,
        "recommended_route": recommend_route(checks, route),
        "exact_commands": build_exact_commands(route),
        "environment_fix_required": status == BLOCKED,
        "can_retry_without_code_changes": status in {PASS, BLOCKED},
        "settings": {
            "database_url": _sanitize_url(database_url),
            "qdrant_url": qdrant_url,
            "qdrant_collection": qdrant_collection,
            "embedding_model": embedding_model,
            "timeout_seconds": timeout_seconds,
            "require_docker_compose": require_docker_compose,
            "external_services_ok": external_services_ok,
        },
        "checks": checks,
        "blocking_checks": [check for check in checks if check["status"] in {FAIL, BLOCKED}],
        "warnings": [check for check in checks if check["status"] == WARN],
        "next_actions": build_next_actions(checks, route),
    }
    payload["human_summary"] = build_human_summary(payload)
    write_json(evidence_dir / "local_proof_doctor_report.json", payload)
    (evidence_dir / "local_proof_doctor_report.md").write_text(render_doctor_markdown(payload), encoding="utf-8")
    return payload


def check_python_version() -> dict[str, Any]:
    version = sys.version_info
    version_text = f"{version.major}.{version.minor}.{version.micro}"
    ok = (version.major, version.minor) >= (3, 11)
    return make_check(
        check_id="python_version",
        component="Python",
        status=PASS if ok else FAIL,
        details={"version": version_text, "required": ">=3.11"},
        remediation=["Install Python 3.11 or newer and recreate the virtual environment."] if not ok else [],
    )


def check_node_version(*, timeout_seconds: int) -> dict[str, Any]:
    return _run_command_check(
        check_id="node_version",
        component="Node.js",
        command=["node", "--version"],
        timeout_seconds=timeout_seconds,
        remediation=["Install Node.js and rerun `npm ci` inside frontend/."],
    )


def check_import_available(check_id: str, component: str, module_name: str, install_command: str) -> dict[str, Any]:
    if importlib.util.find_spec(module_name) is not None:
        return make_check(
            check_id=check_id,
            component=component,
            status=PASS,
            details={"module": module_name, "installed": True},
        )
    return make_check(
        check_id=check_id,
        component=component,
        status=BLOCKED,
        details={"module": module_name, "installed": False},
        remediation=[f"Install missing dependency with `{install_command}`."],
    )


def check_frontend_package_manager() -> dict[str, Any]:
    frontend = PROJECT_ROOT / "frontend"
    package_json = frontend / "package.json"
    lockfiles = {
        "npm": frontend / "package-lock.json",
        "pnpm": frontend / "pnpm-lock.yaml",
        "yarn": frontend / "yarn.lock",
    }
    detected = [name for name, path in lockfiles.items() if path.exists()]
    if package_json.exists() and detected:
        return make_check(
            check_id="frontend_package_manager",
            component="Frontend package manager",
            status=PASS,
            details={"package_json": str(package_json), "detected": detected},
        )
    return make_check(
        check_id="frontend_package_manager",
        component="Frontend package manager",
        status=FAIL,
        details={"package_json_exists": package_json.exists(), "detected": detected},
        remediation=["Restore frontend/package.json and one lockfile, then run the matching install command."],
    )


def check_playwright_browsers() -> dict[str, Any]:
    env_path = os.getenv("PLAYWRIGHT_BROWSERS_PATH")
    cache_candidates = [
        Path(env_path) if env_path else None,
        Path.home() / "AppData" / "Local" / "ms-playwright",
        Path.home() / ".cache" / "ms-playwright",
    ]
    installed_paths: list[Path] = []
    inaccessible_paths: list[str] = []
    for path in cache_candidates:
        if not path or not path.exists():
            continue
        try:
            if any(path.iterdir()):
                installed_paths.append(path)
        except OSError as exc:
            inaccessible_paths.append(f"{path}: {exc}")
    if installed_paths:
        return make_check(
            check_id="playwright_browsers",
            component="Playwright",
            status=PASS,
            details={"installed_paths": [str(path) for path in installed_paths]},
        )
    return make_check(
        check_id="playwright_browsers",
        component="Playwright",
        status=WARN,
        details={"installed_paths": [], "inaccessible_paths": inaccessible_paths},
        remediation=["Run `cd frontend && npx playwright install` before E2E proof."],
    )


def check_docker_config() -> dict[str, Any]:
    config_path = Path.home() / ".docker" / "config.json"
    try:
        config_exists = config_path.exists()
    except OSError as exc:
        return make_check(
            check_id="docker_config",
            component="Docker",
            status=BLOCKED,
            details={"path": str(config_path), "exists": "unknown"},
            errors=[str(exc)],
            remediation=[
                "Fix permissions on the Docker config file or start services outside Codex and use external services.",
            ],
        )
    if not config_exists:
        return make_check(
            check_id="docker_config",
            component="Docker",
            status=WARN,
            details={"path": str(config_path), "exists": False},
            remediation=["Docker config not found. Start Docker Desktop once if Docker CLI authentication is needed."],
        )
    try:
        config_path.read_text(encoding="utf-8")
    except PermissionError as exc:
        return make_check(
            check_id="docker_config",
            component="Docker",
            status=BLOCKED,
            details={"path": str(config_path), "exists": True},
            errors=[str(exc)],
            remediation=[
                "Fix permissions on the Docker config file or start services outside Codex and use external services.",
            ],
        )
    except OSError as exc:
        return make_check(
            check_id="docker_config",
            component="Docker",
            status=BLOCKED,
            details={"path": str(config_path), "exists": True},
            errors=[str(exc)],
            remediation=["Inspect the Docker config file and restore read access for the current Windows user."],
        )
    return make_check(
        check_id="docker_config",
        component="Docker",
        status=PASS,
        details={"path": str(config_path), "exists": True},
    )


def check_docker_cli(*, timeout_seconds: int) -> dict[str, Any]:
    return _run_command_check(
        check_id="docker_cli",
        component="Docker",
        command=["docker", "version", "--format", "{{json .}}"],
        timeout_seconds=timeout_seconds,
        remediation=[
            "Start Docker Desktop and confirm the current user can access the Docker engine.",
            "On Windows, verify access to npipe:////./pipe/docker_engine.",
        ],
    )


def check_docker_compose(*, timeout_seconds: int) -> dict[str, Any]:
    return _run_command_check(
        check_id="docker_compose",
        component="Docker Compose",
        command=["docker", "compose", "config", "--services"],
        timeout_seconds=timeout_seconds,
        remediation=["Run `make local-services-up` in a shell with Docker access or provide already-running services."],
    )


def check_env_configuration(
    *,
    database_url: str,
    qdrant_url: str,
    qdrant_collection: str,
    embedding_model: str,
) -> dict[str, Any]:
    defaults_used = []
    if "PRODUCT_DB_URL" not in os.environ and database_url == DEFAULT_POSTGRES_URL:
        defaults_used.append("PRODUCT_DB_URL")
    if "QDRANT_URL" not in os.environ and qdrant_url == DEFAULT_QDRANT_URL:
        defaults_used.append("QDRANT_URL")
    if "QDRANT_COLLECTION" not in os.environ and qdrant_collection == DEFAULT_QDRANT_COLLECTION:
        defaults_used.append("QDRANT_COLLECTION")
    if "RAG_EMBEDDING_MODEL" not in os.environ and embedding_model == DEFAULT_EMBEDDING_MODEL:
        defaults_used.append("RAG_EMBEDDING_MODEL")
    return make_check(
        check_id="env_configuration",
        component="Configuration",
        status=WARN if defaults_used else PASS,
        details={
            "database_url": _sanitize_url(database_url),
            "qdrant_url": qdrant_url,
            "qdrant_collection": qdrant_collection,
            "embedding_model": embedding_model,
            "defaults_used": defaults_used,
        },
        remediation=(
            ["Set explicit PRODUCT_DB_URL, QDRANT_URL, QDRANT_COLLECTION, and RAG_EMBEDDING_MODEL in .env."]
            if defaults_used
            else []
        ),
    )


def check_tcp_port(check_id: str, component: str, host: str, port: int, *, timeout_seconds: int = 2) -> dict[str, Any]:
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return make_check(
                check_id=check_id,
                component=component,
                status=PASS,
                details={"host": host, "port": port, "open": True},
            )
    except OSError as exc:
        return make_check(
            check_id=check_id,
            component=component,
            status=BLOCKED,
            details={"host": host, "port": port, "open": False},
            errors=[str(exc)],
            remediation=[f"Start the service listening on {host}:{port} or update the env var for this endpoint."],
        )


def check_postgres_connection(database_url: str, *, timeout_seconds: int) -> dict[str, Any]:
    try:
        from sqlalchemy import create_engine, text
        from sqlalchemy.exc import SQLAlchemyError
    except ModuleNotFoundError as exc:
        return make_check(
            check_id="postgres_connection",
            component="PostgreSQL",
            status=BLOCKED,
            details={"database_url": _sanitize_url(database_url), "sqlalchemy_installed": False},
            errors=[str(exc)],
            remediation=["Install backend dependencies with `pip install -e .[postgres]` or `pip install -e .[full]`."],
        )
    try:
        engine = create_engine(
            database_url,
            connect_args=(
                {"connect_timeout": timeout_seconds}
                if database_url.startswith(("postgresql://", "postgresql+psycopg://", "postgresql+psycopg2://"))
                else {}
            ),
            future=True,
            pool_pre_ping=True,
        )
        with engine.connect() as connection:
            scalar = connection.execute(text("SELECT 1")).scalar_one()
        engine.dispose()
        return make_check(
            check_id="postgres_connection",
            component="PostgreSQL",
            status=PASS,
            details={"database_url": _sanitize_url(database_url), "roundtrip_scalar": scalar},
        )
    except SQLAlchemyError as exc:
        return make_check(
            check_id="postgres_connection",
            component="PostgreSQL",
            status=BLOCKED,
            details={"database_url": _sanitize_url(database_url)},
            errors=[str(exc)],
            remediation=["Start PostgreSQL locally or set PRODUCT_DB_URL to a reachable PostgreSQL database."],
        )


def check_qdrant_service(qdrant_url: str, *, timeout_seconds: int) -> dict[str, Any]:
    try:
        with urlopen(f"{qdrant_url.rstrip('/')}/collections", timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return make_check(
            check_id="qdrant_service",
            component="Qdrant",
            status=PASS,
            details={"qdrant_url": qdrant_url, "raw_status": payload.get("status")},
        )
    except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return make_check(
            check_id="qdrant_service",
            component="Qdrant",
            status=BLOCKED,
            details={"qdrant_url": qdrant_url},
            errors=[str(exc)],
            remediation=["Start Qdrant locally or set QDRANT_URL to a reachable Qdrant instance."],
        )


def check_qdrant_collection(qdrant_url: str, collection: str, *, timeout_seconds: int) -> dict[str, Any]:
    try:
        with urlopen(f"{qdrant_url.rstrip('/')}/collections/{collection}", timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        result = payload.get("result", {})
        return make_check(
            check_id="qdrant_collection",
            component="Qdrant",
            status=PASS,
            details={
                "qdrant_url": qdrant_url,
                "collection": collection,
                "points_count": result.get("points_count"),
                "vectors_count": result.get("vectors_count"),
            },
        )
    except HTTPError as exc:
        if exc.code == 404:
            return make_check(
                check_id="qdrant_collection",
                component="Qdrant",
                status=WARN,
                details={"qdrant_url": qdrant_url, "collection": collection, "exists": False},
                remediation=["Run corpus ingestion; the full proof can create/populate this collection."],
            )
        return _qdrant_collection_blocked(qdrant_url, collection, exc)
    except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return _qdrant_collection_blocked(qdrant_url, collection, exc)


def check_alembic_configuration() -> dict[str, Any]:
    alembic_ini = PROJECT_ROOT / "alembic.ini"
    script_location = _read_alembic_script_location(alembic_ini)
    migrations = PROJECT_ROOT / script_location if script_location else PROJECT_ROOT / "migrations"
    versions = migrations / "versions"
    if alembic_ini.exists() and migrations.exists() and versions.exists():
        return make_check(
            check_id="alembic_configuration",
            component="Alembic",
            status=PASS,
            details={
                "alembic_ini": str(alembic_ini),
                "script_location": str(migrations),
                "versions_dir": str(versions),
            },
        )
    return make_check(
        check_id="alembic_configuration",
        component="Alembic",
        status=FAIL,
        details={
            "alembic_ini_exists": alembic_ini.exists(),
            "script_location": str(migrations),
            "script_location_exists": migrations.exists(),
            "versions_dir_exists": versions.exists(),
        },
        remediation=["Restore Alembic configuration before running product proof."],
    )


def check_nvidia_corpus() -> dict[str, Any]:
    corpus_dir = PROJECT_ROOT / "data" / "nvidia_corpus"
    sources = corpus_dir / "sources.yaml"
    md_files = [path for path in corpus_dir.glob("*.md") if path.name != "README.md"] if corpus_dir.exists() else []
    if sources.exists() and md_files:
        return make_check(
            check_id="nvidia_corpus",
            component="RAG Corpus",
            status=PASS,
            details={"sources_yaml": str(sources), "markdown_documents": len(md_files)},
        )
    return make_check(
        check_id="nvidia_corpus",
        component="RAG Corpus",
        status=FAIL,
        details={
            "corpus_dir": str(corpus_dir),
            "sources_yaml_exists": sources.exists(),
            "markdown_documents": len(md_files),
        },
        remediation=["Restore data/nvidia_corpus with sources.yaml and versioned NVIDIA corpus markdown files."],
    )


def check_embedding_provider(model_name: str) -> dict[str, Any]:
    if importlib.util.find_spec("sentence_transformers") is None:
        return make_check(
            check_id="embedding_provider",
            component="RAG Embeddings",
            status=BLOCKED,
            details={"model_name": model_name, "sentence_transformers_installed": False},
            remediation=["Install the RAG extra or package: `pip install -e .[rag]`."],
        )
    cache_hint = _find_embedding_cache_hint(model_name)
    return make_check(
        check_id="embedding_provider",
        component="RAG Embeddings",
        status=PASS if cache_hint else WARN,
        details={
            "model_name": model_name,
            "sentence_transformers_installed": True,
            "cache_hint": str(cache_hint) if cache_hint else "",
        },
        remediation=(
            ["Warm the embedding model cache before offline proof if network is unavailable."] if not cache_hint else []
        ),
    )


def resolve_service_route(
    checks: list[dict[str, Any]],
    *,
    require_docker_compose: bool,
    external_services_ok: bool,
) -> str:
    docker_ready = _status(checks, "docker_cli") == PASS and _status(checks, "docker_compose") == PASS
    external_ready = _status(checks, "postgres_connection") == PASS and _status(checks, "qdrant_service") == PASS
    if require_docker_compose:
        return "docker_compose" if docker_ready else "blocked_require_docker_compose"
    if external_services_ok and external_ready:
        return "external_services"
    if docker_ready:
        return "docker_compose"
    return "blocked_no_service_route"


def aggregate_doctor_status(
    checks: list[dict[str, Any]],
    *,
    require_docker_compose: bool,
    external_services_ok: bool,
) -> str:
    if any(check["status"] == FAIL for check in checks):
        return FAIL
    route = resolve_service_route(
        checks,
        require_docker_compose=require_docker_compose,
        external_services_ok=external_services_ok,
    )
    if route.startswith("blocked"):
        return BLOCKED
    if _status(checks, "embedding_provider") == BLOCKED:
        return BLOCKED
    return PASS


def build_next_actions(checks: list[dict[str, Any]], route: str) -> list[str]:
    actions: list[str] = []
    for check in checks:
        if check["status"] in {FAIL, BLOCKED}:
            actions.extend(check.get("remediation", []))
    if route == "external_services":
        actions.append("Docker is not required for this run because PostgreSQL and Qdrant are already reachable.")
    if route == "blocked_no_service_route":
        actions.append("Either fix Docker access or start PostgreSQL and Qdrant outside Codex, then rerun the proof.")
    return list(dict.fromkeys(actions))


def recommend_route(checks: list[dict[str, Any]], route: str) -> str:
    if route == "external_services":
        return "Use already-running PostgreSQL and Qdrant via env vars, then run full proof."
    if route == "docker_compose":
        return "Use Docker Compose local services, preserving existing volumes and collections."
    docker_blocked = _status(checks, "docker_cli") == BLOCKED or _status(checks, "docker_config") == BLOCKED
    if docker_blocked:
        return "Fix Docker access or start PostgreSQL and Qdrant outside Codex, then rerun full proof."
    return "Start PostgreSQL and Qdrant, then rerun full proof."


def build_exact_commands(route: str) -> list[str]:
    doctor = "python scripts/local_proof_doctor.py"
    prove = "python scripts/prove_final_product.py --full --skip-live"
    if route == "external_services":
        return [
            "set PRODUCT_DB_URL=postgresql://postgres:postgres@localhost:5432/startup_radar",
            "set QDRANT_URL=http://localhost:6333",
            "set QDRANT_COLLECTION=nvidia_corpus",
            doctor,
            prove,
        ]
    if route == "docker_compose":
        return [
            doctor,
            "docker compose up -d postgres qdrant",
            prove,
        ]
    return [
        doctor,
        "docker compose up -d postgres qdrant",
        prove,
        "# If Docker is blocked, start PostgreSQL/Qdrant externally and set PRODUCT_DB_URL/QDRANT_URL.",
    ]


def build_human_summary(payload: dict[str, Any]) -> str:
    status = payload["status"]
    route = payload["effective_service_route"]
    blockers = [
        str(check.get("check_id", "unknown")) for check in payload.get("blocking_checks", []) if isinstance(check, dict)
    ]
    if status == PASS:
        return f"Doctor passed via {route}. The full proof can be retried without code changes."
    if status == FAIL:
        return f"Doctor found a product/repository failure: {', '.join(blockers) or 'unknown'}."
    return (
        f"Doctor is blocked by environment via {route}. Blocking checks: {', '.join(blockers) or 'unknown'}. "
        "Fix services or provide external PostgreSQL/Qdrant, then retry without code changes."
    )


def render_doctor_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Local Proof Doctor",
        "",
        f"Status: `{payload['status']}`",
        f"Effective route: `{payload['effective_service_route']}`",
        f"Recommended route: {payload['recommended_route']}",
        f"Environment fix required: `{payload['environment_fix_required']}`",
        f"Can retry without code changes: `{payload['can_retry_without_code_changes']}`",
        "",
        payload["human_summary"],
        "",
        "## Exact Commands",
        "",
    ]
    lines.extend(f"- `{command}`" for command in payload["exact_commands"])
    lines.extend(["", "## Blocking Checks", ""])
    blockers = payload.get("blocking_checks", [])
    if blockers:
        lines.extend(f"- `{check['check_id']}`: {', '.join(check.get('remediation', []))}" for check in blockers)
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def _run_command_check(
    *,
    check_id: str,
    component: str,
    command: list[str],
    timeout_seconds: int,
    remediation: list[str],
) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        return make_check(
            check_id=check_id,
            component=component,
            status=BLOCKED,
            details={"command": " ".join(command)},
            errors=[str(exc)],
            remediation=remediation,
        )
    except subprocess.TimeoutExpired as exc:
        return make_check(
            check_id=check_id,
            component=component,
            status=BLOCKED,
            details={"command": " ".join(command), "timeout_seconds": timeout_seconds},
            errors=[f"Timed out after {exc.timeout} seconds."],
            remediation=remediation,
        )
    return make_check(
        check_id=check_id,
        component=component,
        status=PASS if result.returncode == 0 else BLOCKED,
        details={
            "command": " ".join(command),
            "returncode": result.returncode,
            "stdout_tail": result.stdout[-2000:],
            "stderr_tail": result.stderr[-2000:],
        },
        errors=[] if result.returncode == 0 else [result.stderr[-2000:] or result.stdout[-2000:] or "Command failed."],
        remediation=[] if result.returncode == 0 else remediation,
    )


def _qdrant_collection_blocked(qdrant_url: str, collection: str, exc: BaseException) -> dict[str, Any]:
    return make_check(
        check_id="qdrant_collection",
        component="Qdrant",
        status=BLOCKED,
        details={"qdrant_url": qdrant_url, "collection": collection},
        errors=[str(exc)],
        remediation=["Make Qdrant reachable before validating or ingesting the configured collection."],
    )


def _postgres_host_port(database_url: str) -> tuple[str, int]:
    try:
        from sqlalchemy.engine import make_url

        parsed = make_url(database_url)
        return parsed.host or "localhost", parsed.port or 5432
    except Exception:
        parsed = urlparse(database_url)
        return parsed.hostname or "localhost", parsed.port or 5432


def _qdrant_host_port(qdrant_url: str) -> tuple[str, int]:
    parsed = urlparse(qdrant_url)
    return parsed.hostname or "localhost", parsed.port or (443 if parsed.scheme == "https" else 6333)


def _read_alembic_script_location(alembic_ini: Path) -> str:
    if not alembic_ini.exists():
        return "migrations"
    config = configparser.ConfigParser()
    config.read(alembic_ini, encoding="utf-8")
    return config.get("alembic", "script_location", fallback="migrations")


def _find_embedding_cache_hint(model_name: str) -> Path | None:
    candidates = [
        Path(os.getenv("SENTENCE_TRANSFORMERS_HOME", "")),
        Path(os.getenv("HF_HOME", "")) / "hub",
        Path.home() / ".cache" / "huggingface" / "hub",
    ]
    model_token = "models--" + model_name.replace("/", "--")
    for candidate in candidates:
        if not str(candidate) or not candidate.exists():
            continue
        direct = candidate / model_token
        if direct.exists():
            return direct
        for child in candidate.glob(f"*{model_name.split('/')[-1]}*"):
            if child.exists():
                return child
    return None


def _status(checks: list[dict[str, Any]], check_id: str) -> str:
    for check in checks:
        if check["check_id"] == check_id:
            return str(check["status"])
    return BLOCKED


def _sanitize_url(value: str) -> str:
    if "@" not in value:
        return value
    prefix, suffix = value.rsplit("@", 1)
    scheme, _credentials = prefix.split("://", 1)
    return f"{scheme}://***:***@{suffix}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    load_product_env()
    parser = argparse.ArgumentParser(description="Diagnose local requirements for full product proof.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--database-url", default=os.getenv("PRODUCT_DB_URL", DEFAULT_POSTGRES_URL))
    parser.add_argument("--qdrant-url", default=os.getenv("QDRANT_URL", DEFAULT_QDRANT_URL))
    parser.add_argument("--qdrant-collection", default=os.getenv("QDRANT_COLLECTION", DEFAULT_QDRANT_COLLECTION))
    parser.add_argument("--embedding-model", default=os.getenv("RAG_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL))
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--require-docker-compose", action="store_true")
    parser.add_argument("--external-services-ok", dest="external_services_ok", action="store_true")
    parser.add_argument("--no-external-services-ok", dest="external_services_ok", action="store_false")
    parser.set_defaults(external_services_ok=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = run_doctor(
        evidence_dir=args.evidence_dir,
        database_url=args.database_url,
        qdrant_url=args.qdrant_url,
        qdrant_collection=args.qdrant_collection,
        embedding_model=args.embedding_model,
        timeout_seconds=args.timeout_seconds,
        require_docker_compose=args.require_docker_compose,
        external_services_ok=args.external_services_ok,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"LOCAL_PROOF_DOCTOR_STATUS={payload['status']}")
    return 1 if payload["status"] == FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
