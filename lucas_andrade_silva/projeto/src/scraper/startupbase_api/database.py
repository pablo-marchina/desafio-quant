from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import psycopg2
from psycopg2.extras import Json, execute_values

from .config import required_env

SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE TABLE IF NOT EXISTS startups_brazil (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    startupbase_id CHAR(64) NOT NULL,
    remote_id TEXT,
    company_name TEXT NOT NULL,
    description TEXT,
    segment TEXT,
    stage TEXT,
    location TEXT,
    founding_year TEXT,
    source_name TEXT,
    source_url TEXT,
    raw_data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE startups_brazil
    ADD COLUMN IF NOT EXISTS startupbase_id CHAR(64),
    ADD COLUMN IF NOT EXISTS remote_id TEXT,
    ADD COLUMN IF NOT EXISTS description TEXT,
    ADD COLUMN IF NOT EXISTS segment TEXT,
    ADD COLUMN IF NOT EXISTS stage TEXT,
    ADD COLUMN IF NOT EXISTS location TEXT,
    ADD COLUMN IF NOT EXISTS founding_year TEXT,
    ADD COLUMN IF NOT EXISTS source_name TEXT,
    ADD COLUMN IF NOT EXISTS source_url TEXT,
    ADD COLUMN IF NOT EXISTS raw_data JSONB;
ALTER TABLE startups_brazil
    ALTER COLUMN location DROP NOT NULL,
    ALTER COLUMN founding_year DROP NOT NULL,
    ALTER COLUMN source_url DROP NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS startups_brazil_startupbase_id_uidx
    ON startups_brazil (startupbase_id);
CREATE INDEX IF NOT EXISTS startups_brazil_company_name_idx ON startups_brazil (LOWER(company_name));
CREATE INDEX IF NOT EXISTS startups_brazil_segment_idx ON startups_brazil (LOWER(segment));
"""


def connect():
    return psycopg2.connect(required_env("DATABASE_URL"))


def ensure_schema(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(SCHEMA_SQL)
    connection.commit()


def upsert_startups(rows: Iterable[dict[str, Any]], connection) -> int:
    materialized = list(rows)
    if not materialized:
        return 0
    values = [
        (
            r["startupbase_id"],
            r.get("remote_id"),
            r["company_name"],
            r.get("description"),
            r.get("segment"),
            r.get("stage"),
            r.get("location"),
            (r.get("founding_date") or "")[:4] or None,
            r.get("source_name"),
            r.get("source_url"),
            Json(r["raw_data"]),
        )
        for r in materialized
    ]
    with connection.cursor() as cursor:
        execute_values(cursor, """INSERT INTO startups_brazil
            (startupbase_id,remote_id,company_name,description,segment,stage,location,founding_year,source_name,source_url,raw_data)
            VALUES %s ON CONFLICT (startupbase_id) DO UPDATE SET
            remote_id=EXCLUDED.remote_id,company_name=EXCLUDED.company_name,description=EXCLUDED.description,
            segment=EXCLUDED.segment,stage=EXCLUDED.stage,location=EXCLUDED.location,
            founding_year=EXCLUDED.founding_year,source_name=EXCLUDED.source_name,
            source_url=EXCLUDED.source_url,raw_data=EXCLUDED.raw_data,updated_at=NOW()""", values, page_size=500)
    connection.commit()
    return len(materialized)
