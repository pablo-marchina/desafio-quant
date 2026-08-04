from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable

import psycopg2
from psycopg2.extras import RealDictCursor, execute_values

SCHEMA_SQL = (Path(__file__).with_name("schema.sql")).read_text(encoding="utf-8")


def create_validated_table_if_not_exists(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(SCHEMA_SQL)
    connection.commit()


def load_raw_supabase(connection, table: str = "startups_brazil") -> list[dict[str, Any]]:
    if not table.replace("_", "").isalnum():
        raise ValueError("Invalid source table name")
    with connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s", (table,))
        columns = {row["column_name"] for row in cursor.fetchall()}
        required = {"company_name", "description", "source_url"}
        missing = required - columns
        if missing:
            raise RuntimeError(f"Raw table {table} is missing columns: {sorted(missing)}")
        source_expr = "source_name" if "source_name" in columns else "NULL::TEXT AS source_name"
        id_expr = "id::TEXT AS raw_company_id" if "id" in columns else "NULL::TEXT AS raw_company_id"
        year_expr = "founding_year" if "founding_year" in columns else "NULL::TEXT AS founding_year"
        cursor.execute(f"SELECT {id_expr}, company_name, description, source_url, {source_expr}, {year_expr} FROM {table}")
        return [dict(row) for row in cursor.fetchall()]


def load_raw_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def upsert_validated_supabase(rows: Iterable[dict[str, Any]], connection) -> int:
    rows = list(rows)
    if not rows:
        return 0
    fields = ("raw_company_id","company_name","normalized_name","source_name","source_url",
        "is_valid_company","is_brazilian","is_startup","uses_ai_potentially","ai_classification",
        "foundation_year","priority","validation_status","rejection_reason","evidence_text",
        "evidence_urls","confidence_score")
    values = [tuple(row.get(field) for field in fields) for row in rows]
    with connection.cursor() as cursor:
        execute_values(cursor, f"""INSERT INTO validated_startup_candidates ({','.join(fields)}) VALUES %s
            ON CONFLICT (normalized_name) DO UPDATE SET
            raw_company_id=EXCLUDED.raw_company_id,company_name=EXCLUDED.company_name,
            source_name=EXCLUDED.source_name,source_url=EXCLUDED.source_url,
            is_valid_company=EXCLUDED.is_valid_company,is_brazilian=EXCLUDED.is_brazilian,
            is_startup=EXCLUDED.is_startup,uses_ai_potentially=EXCLUDED.uses_ai_potentially,
            ai_classification=EXCLUDED.ai_classification,foundation_year=EXCLUDED.foundation_year,
            priority=EXCLUDED.priority,validation_status=EXCLUDED.validation_status,
            rejection_reason=EXCLUDED.rejection_reason,evidence_text=EXCLUDED.evidence_text,
            evidence_urls=ARRAY(SELECT DISTINCT x FROM unnest(validated_startup_candidates.evidence_urls || EXCLUDED.evidence_urls) x),
            confidence_score=EXCLUDED.confidence_score,updated_at=NOW()""", values, page_size=500)
    connection.commit()
    return len(rows)
