from __future__ import annotations

import argparse
import json
import logging
import os
from collections import Counter
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

from .database import create_validated_table_if_not_exists, load_raw_csv, load_raw_supabase, upsert_validated_supabase
from .validator import validate_candidate

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _deduplicate(rows: list[dict]) -> tuple[list[dict], int]:
    best: dict[str, dict] = {}
    for row in rows:
        key = row["normalized_name"]
        if not key:
            continue
        current = best.get(key)
        if current is None or row["confidence_score"] > current["confidence_score"]:
            best[key] = row
    return list(best.values()), len(rows) - len(best)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate raw startup candidates without modifying the raw source.")
    parser.add_argument("--source-table", default="startups_brazil")
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    load_dotenv(PROJECT_ROOT / ".env")
    database_url = os.getenv("DATABASE_URL")
    if not args.csv and not database_url:
        raise RuntimeError("DATABASE_URL is required when --csv is not used")
    connection = psycopg2.connect(database_url) if database_url else None
    try:
        raw = load_raw_csv(args.csv) if args.csv else load_raw_supabase(connection, args.source_table)
        validated, duplicates = _deduplicate([validate_candidate(row) for row in raw])
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(validated, ensure_ascii=False, indent=2), encoding="utf-8")
        if not args.dry_run:
            if connection is None:
                if not database_url: raise RuntimeError("DATABASE_URL is required to upsert")
                connection = psycopg2.connect(database_url)
            create_validated_table_if_not_exists(connection)
            upsert_validated_supabase(validated, connection)
        statuses = Counter(row["validation_status"] for row in validated)
        ai = Counter(row["ai_classification"] for row in validated)
        print(json.dumps({"total_raw": len(raw), "deduplicated": len(validated), "duplicates": duplicates,
            "approved": statuses["APPROVED"], "review": statuses["REVIEW"], "rejected": statuses["REJECTED"],
            "potential_ai": sum(row["uses_ai_potentially"] is True for row in validated),
            "AI_NATIVE": ai["AI_NATIVE"], "AI_ENABLED": ai["AI_ENABLED"], "NON_AI": ai["NON_AI"],
            "upserted": 0 if args.dry_run else len(validated), "dry_run": args.dry_run}, ensure_ascii=False, indent=2))
    finally:
        if connection is not None: connection.close()


if __name__ == "__main__":
    main()
