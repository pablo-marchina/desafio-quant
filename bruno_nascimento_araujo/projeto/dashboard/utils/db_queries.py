"""Consultas ao PostgreSQL para o dashboard (somente leitura).

Pool cacheado via @st.cache_resource (seguro porque sempre roda no mesmo loop
de background — ver agent_calls.py); resultados de query cacheados via
@st.cache_data(ttl=600).

IMPORTANTE: get_pool() é sempre chamado FORA da coroutine interna (_query),
nunca de dentro dela. get_pool() já faz sua própria chamada a run_async() na
primeira vez que roda; se essa primeira chamada acontecer de DENTRO de uma
coroutine que já está executando na thread do loop de background (ex: se
fosse chamado dentro de _query, que já roda lá via run_async), o
future.result() bloqueante do get_pool() trava esperando a própria thread do
loop, que está ocupada esperando nele — deadlock. Chamando get_pool() no
código síncrono (a thread do próprio Streamlit), esse problema não existe.
"""
from __future__ import annotations

import json

import asyncpg
import streamlit as st

from src.config import get_settings

from .agent_calls import run_async


@st.cache_resource
def get_pool() -> asyncpg.Pool:
    async def _create() -> asyncpg.Pool:
        settings = get_settings()
        return await asyncpg.create_pool(settings.database_url, min_size=2, max_size=10)
    return run_async(_create())


@st.cache_data(ttl=600)
def fetch_dashboard_summary() -> dict:
    pool = get_pool()

    async def _query() -> dict:
        row = await pool.fetchrow(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE classification = 'ai_native')  AS ai_native,
                COUNT(*) FILTER (WHERE classification = 'ai_enabled') AS ai_enabled,
                COUNT(*) FILTER (WHERE classification = 'non_ai')     AS non_ai
            FROM classifications
            """
        )
        return dict(row)
    return run_async(_query())


@st.cache_data(ttl=600)
def fetch_sector_counts() -> list[dict]:
    pool = get_pool()

    async def _query() -> list[dict]:
        rows = await pool.fetch(
            """
            SELECT sd.sector, COUNT(*) AS total
            FROM startups_discovered sd
            JOIN classifications c ON c.startup_id = sd.id
            WHERE sd.sector IS NOT NULL
            GROUP BY sd.sector
            ORDER BY total DESC
            """
        )
        return [dict(r) for r in rows]
    return run_async(_query())


@st.cache_data(ttl=600)
def fetch_sectors() -> list[str]:
    pool = get_pool()

    async def _query() -> list[str]:
        rows = await pool.fetch(
            "SELECT DISTINCT sector FROM startups_discovered WHERE sector IS NOT NULL ORDER BY sector"
        )
        return [r["sector"] for r in rows]
    return run_async(_query())


@st.cache_data(ttl=600)
def fetch_startup_list(
    classification: str | None = None, sector: str | None = None, search: str | None = None,
) -> list[dict]:
    pool = get_pool()

    async def _query() -> list[dict]:
        conditions, params = [], []
        if classification:
            params.append(classification)
            conditions.append(f"c.classification = ${len(params)}")
        if sector:
            params.append(sector)
            conditions.append(f"sd.sector = ${len(params)}")
        if search:
            params.append(f"%{search}%")
            conditions.append(f"sd.name ILIKE ${len(params)}")
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = await pool.fetch(
            f"""
            SELECT sd.id, sd.name, sd.sector, c.classification, c.confidence_score
            FROM startups_discovered sd
            JOIN classifications c ON c.startup_id = sd.id
            {where}
            ORDER BY sd.id
            """,
            *params,
        )
        return [dict(r) for r in rows]
    return run_async(_query())


@st.cache_data(ttl=600)
def fetch_startup_detail(startup_id: int) -> dict | None:
    pool = get_pool()

    async def _query() -> dict | None:
        row = await pool.fetchrow(
            """
            SELECT sd.id, sd.name, sd.sector, sd.official_website,
                   c.classification, c.confidence_score, c.justification, c.evidence_chunks,
                   r.recommendations,
                   b.report_markdown, b.generated_at AS briefing_generated_at
            FROM startups_discovered sd
            LEFT JOIN classifications c ON c.startup_id = sd.id
            LEFT JOIN recommendations r ON r.startup_id = sd.id
            LEFT JOIN briefings b ON b.startup_id = sd.id
            WHERE sd.id = $1
            """,
            startup_id,
        )
        if not row:
            return None
        d = dict(row)
        if d.get("recommendations"):
            d["recommendations"] = json.loads(d["recommendations"])
        return d
    return run_async(_query())
