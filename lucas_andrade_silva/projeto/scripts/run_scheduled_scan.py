from __future__ import annotations

import argparse
import json
import logging
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scraper.enrichment_pipeline import main as enrichment_main
from scraper.enrichment_pipeline import config as enrichment_config
from scraper.enrichment_pipeline.nodes.update_supabase import ensure_results_schema
from scraper.validation_pipeline import database as validation_database
from scraper.validation_pipeline import main as validation_main
from scraper.validation_pipeline.validator import normalize_company_name

DEFAULT_SOURCE_TABLE = "startups_brazil"
DEFAULT_STATUSES = ("APPROVED", "REVIEW")
DEFAULT_DISCOVERY_COMMAND = "python -m scraper.rss_news.main"
TRUE_VALUES = {"1", "true", "yes", "y", "sim"}


@dataclass(frozen=True)
class CandidateIdentity:
    candidate_id: str
    normalized_name: str
    company_name: str


def _configure_logging() -> None:
    logging.basicConfig(
        level=os.getenv("SCHEDULED_SCAN_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(message)s",
    )


def _split_command(command: str) -> list[str]:
    if os.name == "nt":
        return shlex.split(command, posix=False)
    return shlex.split(command)


def _safe_table_name(value: str) -> str:
    if not value.replace("_", "").isalnum():
        raise ValueError(f"Invalid table name: {value}")
    return value


def _connect():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required for the scheduled scan")
    import psycopg2
    import psycopg2.extras

    return psycopg2.connect(database_url, cursor_factory=psycopg2.extras.RealDictCursor)


def _candidate_identity(row: dict[str, Any]) -> CandidateIdentity:
    return CandidateIdentity(
        candidate_id=str(row.get("id") or row.get("raw_company_id") or "").strip(),
        normalized_name=str(row.get("normalized_name") or normalize_company_name(row.get("company_name"))).strip(),
        company_name=str(row.get("company_name") or "").strip(),
    )


def _load_candidate_identities(statuses: tuple[str, ...]) -> list[CandidateIdentity]:
    table = _safe_table_name(enrichment_config.SUPABASE_TABLE)
    placeholders = ",".join(["%s"] * len(statuses))
    with _connect() as connection:
        validation_database.create_validated_table_if_not_exists(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT id::text AS id, raw_company_id, normalized_name, company_name
                FROM {table}
                WHERE validation_status IN ({placeholders})
                  AND COALESCE(is_active, TRUE) = TRUE
                """,
                statuses,
            )
            return [_candidate_identity(dict(row)) for row in cursor.fetchall()]


def _load_enriched_identities() -> set[str]:
    ensure_results_schema()
    table = _safe_table_name(enrichment_config.ENRICHMENT_RESULTS_TABLE)
    keys: set[str] = set()
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT candidate_id, company_name FROM {table}")
            for row in cursor.fetchall():
                candidate_id = str(row.get("candidate_id") or "").strip()
                company_name = str(row.get("company_name") or "").strip()
                if candidate_id:
                    keys.add(f"id:{candidate_id}")
                normalized = normalize_company_name(company_name)
                if normalized:
                    keys.add(f"name:{normalized}")
    return keys


def _candidate_keys(candidate: CandidateIdentity) -> set[str]:
    keys: set[str] = set()
    if candidate.candidate_id:
        keys.add(f"id:{candidate.candidate_id}")
    if candidate.normalized_name:
        keys.add(f"name:{candidate.normalized_name}")
    return keys


def _run_discovery(command: str) -> None:
    args = _split_command(command)
    env = os.environ.copy()
    current_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        f"{SRC_ROOT}{os.pathsep}{current_pythonpath}"
        if current_pythonpath
        else str(SRC_ROOT)
    )
    logging.info("running startup discovery: %s", command)
    completed = subprocess.run(args, cwd=PROJECT_ROOT, env=env, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"startup discovery failed with exit code {completed.returncode}")


def _run_validation(source_table: str) -> dict[str, Any]:
    logging.info("validating raw candidates from table %s", source_table)
    with _connect() as connection:
        raw = validation_database.load_raw_supabase(connection, source_table)
        validated, duplicates = validation_main._deduplicate(
            [validation_main.validate_candidate(row) for row in raw]
        )
        validation_database.create_validated_table_if_not_exists(connection)
        upserted = validation_database.upsert_validated_supabase(validated, connection)
    summary = {
        "raw_candidates": len(raw),
        "validated_candidates": len(validated),
        "duplicates": duplicates,
        "upserted": upserted,
    }
    logging.info("validation summary: %s", json.dumps(summary, ensure_ascii=False))
    return summary


def _empty_validation_summary() -> dict[str, Any]:
    return {
        "raw_candidates": 0,
        "validated_candidates": 0,
        "duplicates": 0,
        "upserted": 0,
    }


def _new_candidates(
    before: list[CandidateIdentity],
    after: list[CandidateIdentity],
    enriched_keys: set[str],
) -> list[CandidateIdentity]:
    before_keys = {key for candidate in before for key in _candidate_keys(candidate)}
    selected: list[CandidateIdentity] = []
    seen: set[str] = set()
    for candidate in after:
        keys = _candidate_keys(candidate)
        if not keys or keys & before_keys or keys & enriched_keys:
            continue
        stable_key = next(iter(sorted(keys)))
        if stable_key in seen:
            continue
        seen.add(stable_key)
        selected.append(candidate)
    return selected


def _enrich_candidates(
    candidates: list[CandidateIdentity],
    *,
    mode: str,
    no_cache: bool,
) -> tuple[int, int]:
    success = 0
    errors = 0
    for index, candidate in enumerate(candidates, start=1):
        logging.info(
            "enriching candidate %s/%s: %s (%s)",
            index,
            len(candidates),
            candidate.company_name,
            candidate.candidate_id,
        )
        try:
            result = enrichment_main.run(
                company_id=candidate.candidate_id,
                mode=mode,
                reset_checkpoint=False,
                no_cache=no_cache,
            )
            if int(result.get("error") or 0) > 0:
                errors += 1
                logging.error("enrichment reported errors for %s: %s", candidate.company_name, result)
            else:
                success += 1
        except Exception:
            errors += 1
            logging.exception("enrichment failed for %s", candidate.company_name)
    return success, errors


def run(args: argparse.Namespace) -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    _configure_logging()
    source_table = args.source_table or os.getenv("SCHEDULED_SCAN_SOURCE_TABLE", DEFAULT_SOURCE_TABLE)
    statuses = tuple(args.status or DEFAULT_STATUSES)
    logging.info("scheduled startup scan started")
    before_candidates = _load_candidate_identities(statuses)
    enriched_before = _load_enriched_identities()
    logging.info(
        "baseline: %s validated candidates, %s enriched identity keys",
        len(before_candidates),
        len(enriched_before),
    )

    discovery_command = (
        args.discovery_command
        or args.rss_command
        or os.getenv("SCHEDULED_SCAN_DISCOVERY_COMMAND")
        or os.getenv("SCHEDULED_SCAN_RSS_COMMAND")
        or DEFAULT_DISCOVERY_COMMAND
    )
    _run_discovery(discovery_command)
    skip_validation = args.skip_validation or os.getenv("SCHEDULED_SCAN_SKIP_VALIDATION", "").casefold() in TRUE_VALUES
    if skip_validation:
        logging.info("validation skipped because SCHEDULED_SCAN_SKIP_VALIDATION is enabled")
        validation_summary = _empty_validation_summary()
    else:
        validation_summary = _run_validation(source_table)

    after_candidates = _load_candidate_identities(statuses)
    enriched_after_validation = _load_enriched_identities()
    discovered_validated = max(0, len(after_candidates) - len(before_candidates))
    candidates_to_enrich = _new_candidates(before_candidates, after_candidates, enriched_after_validation)
    logging.info(
        "scan summary: raw=%s validated=%s newly_validated=%s new_to_enrich=%s",
        validation_summary["raw_candidates"],
        validation_summary["validated_candidates"],
        discovered_validated,
        len(candidates_to_enrich),
    )

    if not candidates_to_enrich:
        logging.info("nenhuma startup nova encontrada")
        return 0

    success, errors = _enrich_candidates(candidates_to_enrich, mode=args.mode, no_cache=args.no_cache)
    logging.info("enrichment summary: success=%s errors=%s", success, errors)
    logging.info("scheduled startup scan finished")
    return 1 if errors else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run scheduled startup discovery and enrichment.")
    parser.add_argument("--discovery-command", help="Existing startup discovery command to execute before validation.")
    parser.add_argument("--rss-command", help=argparse.SUPPRESS)
    parser.add_argument("--source-table", default=None, help="Raw candidates table populated by the scraper.")
    parser.add_argument("--status", action="append", choices=["APPROVED", "REVIEW", "REJECTED", "DISCARDED"])
    parser.add_argument("--mode", choices=["identity-only", "deep", "full"], default="full")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--skip-validation", action="store_true")
    args = parser.parse_args()
    try:
        raise SystemExit(run(args))
    except Exception:
        logging.exception("scheduled startup scan failed")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
