from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from app.config import Settings
from app.schemas.analysis import (
    EvidenceCheck,
    StartupAnalysisRequest,
    StartupRecommendation,
)
from app.startup_sources import load_startup_candidates, normalize_text


class DatabaseUnavailable(RuntimeError):
    pass


def _import_psycopg():
    try:
        import psycopg
        from psycopg.rows import dict_row
        from psycopg.types.json import Jsonb
    except ModuleNotFoundError as error:
        raise DatabaseUnavailable(
            "Dependencia psycopg nao instalada. Rode: python -m pip install -r requirements.txt"
        ) from error

    return psycopg, dict_row, Jsonb


def database_enabled(settings: Settings) -> bool:
    database_url = (settings.database_url or "").strip().lower()
    return bool(database_url) and database_url not in {"disabled", "none", "off"}


def get_connection(settings: Settings):
    if not database_enabled(settings):
        raise DatabaseUnavailable("NVIDIA_RADAR_DATABASE_URL nao configurado.")

    psycopg, _dict_row, _Jsonb = _import_psycopg()
    return psycopg.connect(settings.database_url)


def ensure_database_schema(settings: Settings) -> None:
    if not database_enabled(settings):
        return

    with get_connection(settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS startups (
                    id UUID PRIMARY KEY,
                    name TEXT NOT NULL,
                    website_url TEXT,
                    sector TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    UNIQUE (name, website_url)
                );

                CREATE TABLE IF NOT EXISTS analysis_runs (
                    id UUID PRIMARY KEY,
                    startup_id UUID NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
                    classification TEXT NOT NULL,
                    ai_native_score INTEGER NOT NULL,
                    wrapper_risk_score INTEGER NOT NULL,
                    nvidia_fit_score INTEGER NOT NULL,
                    detected_gaps JSONB NOT NULL DEFAULT '[]'::jsonb,
                    limitations JSONB NOT NULL DEFAULT '[]'::jsonb,
                    briefing_markdown TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );

                CREATE TABLE IF NOT EXISTS scraped_pages (
                    id BIGSERIAL PRIMARY KEY,
                    analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
                    source_url TEXT NOT NULL,
                    status_code INTEGER,
                    characters INTEGER NOT NULL DEFAULT 0,
                    excerpt TEXT
                );

                CREATE TABLE IF NOT EXISTS recommendations (
                    id BIGSERIAL PRIMARY KEY,
                    analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
                    technology TEXT NOT NULL,
                    category TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    implementation_complexity TEXT NOT NULL DEFAULT 'medium',
                    next_action TEXT NOT NULL DEFAULT '',
                    technical_reason TEXT NOT NULL,
                    business_reason TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    retrieval_score DOUBLE PRECISION NOT NULL
                );

                CREATE TABLE IF NOT EXISTS evidence_checks (
                    id BIGSERIAL PRIMARY KEY,
                    analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
                    claim TEXT NOT NULL,
                    support TEXT NOT NULL,
                    confidence DOUBLE PRECISION NOT NULL,
                    source TEXT NOT NULL,
                    note TEXT NOT NULL,
                    severity TEXT NOT NULL DEFAULT 'info',
                    blocks_recommendation BOOLEAN NOT NULL DEFAULT false,
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
                );

                ALTER TABLE evidence_checks
                    ADD COLUMN IF NOT EXISTS severity TEXT NOT NULL DEFAULT 'info';
                ALTER TABLE evidence_checks
                    ADD COLUMN IF NOT EXISTS blocks_recommendation BOOLEAN NOT NULL DEFAULT false;
                ALTER TABLE evidence_checks
                    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;
                ALTER TABLE recommendations
                    ADD COLUMN IF NOT EXISTS implementation_complexity TEXT NOT NULL DEFAULT 'medium';
                ALTER TABLE recommendations
                    ADD COLUMN IF NOT EXISTS next_action TEXT NOT NULL DEFAULT '';
                ALTER TABLE scraped_pages
                    ADD COLUMN IF NOT EXISTS title TEXT;
                ALTER TABLE scraped_pages
                    ADD COLUMN IF NOT EXISTS source_type TEXT NOT NULL DEFAULT 'startup_page';
                ALTER TABLE scraped_pages
                    ADD COLUMN IF NOT EXISTS collected_at TEXT;

                CREATE TABLE IF NOT EXISTS startup_catalog (
                    id BIGSERIAL PRIMARY KEY,
                    startup_key TEXT NOT NULL UNIQUE,
                    startup_name TEXT NOT NULL,
                    country_code TEXT NOT NULL DEFAULT 'BR',
                    sector TEXT NOT NULL DEFAULT 'unknown',
                    stage TEXT,
                    source TEXT NOT NULL,
                    website_url TEXT,
                    github_url TEXT,
                    source_url TEXT,
                    description TEXT NOT NULL DEFAULT '',
                    signals JSONB NOT NULL DEFAULT '[]'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );

                CREATE TABLE IF NOT EXISTS startup_discoveries (
                    id BIGSERIAL PRIMARY KEY,
                    discovery_key TEXT NOT NULL UNIQUE,
                    startup_key TEXT NOT NULL,
                    startup_name TEXT NOT NULL,
                    country_code TEXT NOT NULL DEFAULT 'BR',
                    sector TEXT NOT NULL DEFAULT 'unknown',
                    stage TEXT,
                    source TEXT NOT NULL,
                    website_url TEXT,
                    github_url TEXT,
                    source_url TEXT,
                    article_title TEXT NOT NULL DEFAULT '',
                    article_url TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    signals JSONB NOT NULL DEFAULT '[]'::jsonb,
                    confidence INTEGER NOT NULL DEFAULT 0,
                    discovered_at TIMESTAMPTZ,
                    status TEXT NOT NULL DEFAULT 'new',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );

                CREATE TABLE IF NOT EXISTS nvidia_source_registry (
                    id BIGSERIAL PRIMARY KEY,
                    product_name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    source_url TEXT NOT NULL UNIQUE,
                    source_type TEXT NOT NULL DEFAULT 'official_docs',
                    is_active BOOLEAN NOT NULL DEFAULT true,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );

                CREATE TABLE IF NOT EXISTS nvidia_document_versions (
                    id BIGSERIAL PRIMARY KEY,
                    source_url TEXT NOT NULL,
                    product_name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    modified_at TEXT,
                    content_hash TEXT NOT NULL,
                    characters INTEGER NOT NULL DEFAULT 0,
                    collected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    is_current BOOLEAN NOT NULL DEFAULT true
                );

                CREATE TABLE IF NOT EXISTS nvidia_update_checks (
                    id BIGSERIAL PRIMARY KEY,
                    source_url TEXT NOT NULL,
                    product_name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    local_content_hash TEXT,
                    remote_content_hash TEXT,
                    local_modified_at TEXT,
                    remote_modified_at TEXT,
                    status TEXT NOT NULL,
                    action TEXT NOT NULL,
                    is_useful_for_startups BOOLEAN NOT NULL DEFAULT false,
                    usefulness_score INTEGER NOT NULL DEFAULT 0,
                    useful_topics JSONB NOT NULL DEFAULT '[]'::jsonb,
                    usefulness_reason TEXT NOT NULL DEFAULT '',
                    characters INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT
                );

                CREATE INDEX IF NOT EXISTS analysis_runs_created_at_idx
                    ON analysis_runs (created_at DESC);
                CREATE INDEX IF NOT EXISTS recommendations_technology_idx
                    ON recommendations (technology);
                CREATE INDEX IF NOT EXISTS startup_catalog_sector_idx
                    ON startup_catalog (sector);
                CREATE INDEX IF NOT EXISTS startup_discoveries_confidence_idx
                    ON startup_discoveries (confidence DESC);
                CREATE INDEX IF NOT EXISTS nvidia_document_versions_source_idx
                    ON nvidia_document_versions (source_url, collected_at DESC);
                CREATE INDEX IF NOT EXISTS nvidia_update_checks_checked_at_idx
                    ON nvidia_update_checks (checked_at DESC);
                """
            )


def database_health(settings: Settings) -> dict[str, Any]:
    if not database_enabled(settings):
        return {"enabled": False, "status": "not_configured"}

    try:
        with get_connection(settings) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        return {"enabled": True, "status": "ok"}
    except Exception as error:
        return {"enabled": True, "status": "unavailable", "error": str(error)}


def _jsonable(value: Any) -> Any:
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return str(value) if value.__class__.__name__ == "Url" else value


def save_analysis_run(
    settings: Settings,
    request: StartupAnalysisRequest,
    classification: str,
    ai_native_score: int,
    wrapper_risk_score: int,
    nvidia_fit_score: int,
    source_pages: list[dict[str, Any]],
    detected_gaps: list[str],
    recommendations: list[StartupRecommendation],
    evidence_checks: list[EvidenceCheck],
    briefing_markdown: str,
    limitations: list[str],
    analysis_run_id: str | None = None,
) -> str:
    if not database_enabled(settings):
        raise DatabaseUnavailable("NVIDIA_RADAR_DATABASE_URL nao configurado.")

    _psycopg, _dict_row, Jsonb = _import_psycopg()

    startup_id = str(uuid4())
    analysis_run_id = analysis_run_id or str(uuid4())
    website_url = str(request.website_url) if request.website_url else None

    with get_connection(settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO startups (id, name, website_url, sector)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (name, website_url)
                DO UPDATE SET
                    sector = EXCLUDED.sector,
                    updated_at = now()
                RETURNING id
                """,
                (startup_id, request.startup_name, website_url, request.sector),
            )
            saved_startup_id = cursor.fetchone()[0]

            cursor.execute(
                """
                INSERT INTO analysis_runs (
                    id,
                    startup_id,
                    classification,
                    ai_native_score,
                    wrapper_risk_score,
                    nvidia_fit_score,
                    detected_gaps,
                    limitations,
                    briefing_markdown
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    analysis_run_id,
                    saved_startup_id,
                    classification,
                    ai_native_score,
                    wrapper_risk_score,
                    nvidia_fit_score,
                    Jsonb(_jsonable(detected_gaps)),
                    Jsonb(_jsonable(limitations)),
                    briefing_markdown,
                ),
            )

            for page in source_pages:
                cursor.execute(
                    """
                    INSERT INTO scraped_pages (
                        analysis_run_id,
                        source_url,
                        title,
                        source_type,
                        status_code,
                        characters,
                        excerpt,
                        collected_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        analysis_run_id,
                        str(page.get("source_url", "")),
                        page.get("title"),
                        page.get("source_type") or "startup_page",
                        page.get("status_code"),
                        int(page.get("characters") or 0),
                        page.get("excerpt"),
                        page.get("collected_at"),
                    ),
                )

            for recommendation in recommendations:
                cursor.execute(
                    """
                    INSERT INTO recommendations (
                        analysis_run_id,
                        technology,
                        category,
                        priority,
                        implementation_complexity,
                        next_action,
                        technical_reason,
                        business_reason,
                        source_url,
                        retrieval_score
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        analysis_run_id,
                        recommendation.technology,
                        recommendation.category,
                        recommendation.priority,
                        recommendation.implementation_complexity,
                        recommendation.next_action,
                        recommendation.technical_reason,
                        recommendation.business_reason,
                        str(recommendation.source_url),
                        recommendation.retrieval_score,
                    ),
                )

            for evidence in evidence_checks:
                cursor.execute(
                    """
                    INSERT INTO evidence_checks (
                        analysis_run_id,
                        claim,
                        support,
                        confidence,
                        source,
                        note,
                        severity,
                        blocks_recommendation,
                        metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        analysis_run_id,
                        evidence.claim,
                        evidence.support,
                        evidence.confidence,
                        str(evidence.source),
                        evidence.note,
                        evidence.severity,
                        evidence.blocks_recommendation,
                        Jsonb(
                            _jsonable(
                                {
                                    "claim_type": evidence.claim_type,
                                    "evidence_ids": evidence.evidence_ids,
                                    "source_urls": evidence.source_urls,
                                    "recommendation_technology": (
                                        evidence.recommendation_technology
                                    ),
                                    "minimum_required": evidence.minimum_required,
                                    "blocking_reason": evidence.blocking_reason,
                                }
                            )
                        ),
                    ),
                )

    return analysis_run_id


def list_analysis_runs(settings: Settings, limit: int = 20) -> list[dict[str, Any]]:
    if not database_enabled(settings):
        raise DatabaseUnavailable("NVIDIA_RADAR_DATABASE_URL nao configurado.")

    _psycopg, dict_row, _Jsonb = _import_psycopg()
    with _psycopg.connect(settings.database_url, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    ar.id::text AS analysis_run_id,
                    s.name AS startup_name,
                    s.website_url,
                    s.sector,
                    ar.classification,
                    ar.ai_native_score,
                    ar.wrapper_risk_score,
                    ar.nvidia_fit_score,
                    ar.created_at::text AS created_at,
                    COUNT(DISTINCT r.id)::int AS recommendations_count,
                    COUNT(DISTINCT sp.id)::int AS scraped_pages_count
                FROM analysis_runs ar
                JOIN startups s ON s.id = ar.startup_id
                LEFT JOIN recommendations r ON r.analysis_run_id = ar.id
                LEFT JOIN scraped_pages sp ON sp.analysis_run_id = ar.id
                GROUP BY ar.id, s.id
                ORDER BY ar.created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            return list(cursor.fetchall())


def get_analysis_briefing(settings: Settings, analysis_run_id: str) -> dict[str, Any] | None:
    if not database_enabled(settings):
        raise DatabaseUnavailable("NVIDIA_RADAR_DATABASE_URL nao configurado.")

    _psycopg, dict_row, _Jsonb = _import_psycopg()
    with _psycopg.connect(settings.database_url, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    ar.id::text AS analysis_run_id,
                    s.name AS startup_name,
                    ar.briefing_markdown,
                    ar.created_at::text AS created_at
                FROM analysis_runs ar
                JOIN startups s ON s.id = ar.startup_id
                WHERE ar.id = %s
                """,
                (analysis_run_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None


def startup_key(value: object) -> str:
    normalized = normalize_text(value)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    words = [
        word
        for word in normalized.split()
        if word not in {"ltda", "sa", "s", "a", "me", "eireli"}
    ]
    return " ".join(words).strip()


def discovery_key(value: dict[str, Any]) -> str:
    return startup_key(value.get("startup_name"))


def _candidate_row(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "startup_key": startup_key(candidate.get("startup_name")),
        "startup_name": str(candidate.get("startup_name") or "").strip(),
        "country_code": str(candidate.get("country_code") or "BR").strip().upper(),
        "sector": str(candidate.get("sector") or "unknown").strip() or "unknown",
        "stage": str(candidate.get("stage") or "").strip() or None,
        "source": str(candidate.get("source") or "external_source").strip(),
        "website_url": str(candidate.get("website_url") or "").strip() or None,
        "github_url": str(candidate.get("github_url") or "").strip() or None,
        "source_url": str(candidate.get("source_url") or "").strip() or None,
        "description": str(candidate.get("description") or "").strip(),
        "signals": _jsonable(candidate.get("signals") or []),
    }


def upsert_startup_catalog(
    settings: Settings,
    candidates: list[dict[str, Any]],
) -> int:
    if not database_enabled(settings):
        raise DatabaseUnavailable("NVIDIA_RADAR_DATABASE_URL nao configurado.")

    _psycopg, _dict_row, Jsonb = _import_psycopg()
    rows = [_candidate_row(candidate) for candidate in candidates]
    rows = [row for row in rows if row["startup_key"] and row["startup_name"]]
    if not rows:
        return 0

    with get_connection(settings) as connection:
        with connection.cursor() as cursor:
            for row in rows:
                cursor.execute(
                    """
                    INSERT INTO startup_catalog (
                        startup_key,
                        startup_name,
                        country_code,
                        sector,
                        stage,
                        source,
                        website_url,
                        github_url,
                        source_url,
                        description,
                        signals
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (startup_key)
                    DO UPDATE SET
                        startup_name = EXCLUDED.startup_name,
                        country_code = EXCLUDED.country_code,
                        sector = EXCLUDED.sector,
                        stage = EXCLUDED.stage,
                        source = EXCLUDED.source,
                        website_url = COALESCE(EXCLUDED.website_url, startup_catalog.website_url),
                        github_url = COALESCE(EXCLUDED.github_url, startup_catalog.github_url),
                        source_url = COALESCE(EXCLUDED.source_url, startup_catalog.source_url),
                        description = COALESCE(NULLIF(EXCLUDED.description, ''), startup_catalog.description),
                        signals = EXCLUDED.signals,
                        updated_at = now()
                    """,
                    (
                        row["startup_key"],
                        row["startup_name"],
                        row["country_code"],
                        row["sector"],
                        row["stage"],
                        row["source"],
                        row["website_url"],
                        row["github_url"],
                        row["source_url"],
                        row["description"],
                        Jsonb(row["signals"]),
                    ),
                )
    return len(rows)


def list_startup_catalog(settings: Settings) -> list[dict[str, Any]]:
    if not database_enabled(settings):
        raise DatabaseUnavailable("NVIDIA_RADAR_DATABASE_URL nao configurado.")

    psycopg, dict_row, _Jsonb = _import_psycopg()
    with psycopg.connect(settings.database_url, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    startup_name,
                    country_code,
                    sector,
                    stage,
                    source,
                    website_url,
                    github_url,
                    source_url,
                    description,
                    signals
                FROM startup_catalog
                ORDER BY startup_name
                """
            )
            return list(cursor.fetchall())


def startup_catalog_count(settings: Settings) -> int:
    if not database_enabled(settings):
        raise DatabaseUnavailable("NVIDIA_RADAR_DATABASE_URL nao configurado.")

    with get_connection(settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM startup_catalog")
            return int(cursor.fetchone()[0])


def seed_startup_catalog_from_csv(settings: Settings) -> int:
    if not database_enabled(settings):
        return 0
    if startup_catalog_count(settings) > 0:
        return 0

    candidates = load_startup_candidates(settings.startup_source_path)
    return upsert_startup_catalog(settings, candidates)


def catalog_status(settings: Settings) -> dict[str, Any]:
    if not database_enabled(settings):
        return {
            "backend": "csv",
            "status": "database_not_configured",
            "path": settings.startup_source_path,
            "count": len(load_startup_candidates(settings.startup_source_path)),
        }

    try:
        return {
            "backend": "postgres",
            "status": "ok",
            "table": "startup_catalog",
            "seed_path": settings.startup_source_path,
            "count": startup_catalog_count(settings),
        }
    except Exception as error:
        return {
            "backend": "postgres",
            "status": "unavailable",
            "error": str(error),
            "seed_path": settings.startup_source_path,
        }


def _discovery_row(discovery: dict[str, Any]) -> dict[str, Any]:
    article_url = str(discovery.get("article_url") or discovery.get("source_url") or "")
    return {
        "discovery_key": discovery_key(discovery),
        "startup_key": startup_key(discovery.get("startup_name")),
        "startup_name": str(discovery.get("startup_name") or "").strip(),
        "country_code": str(discovery.get("country_code") or "BR").strip().upper(),
        "sector": str(discovery.get("sector") or "unknown").strip() or "unknown",
        "stage": str(discovery.get("stage") or "").strip() or None,
        "source": str(discovery.get("source") or "external_source").strip(),
        "website_url": str(discovery.get("website_url") or "").strip() or None,
        "github_url": str(discovery.get("github_url") or "").strip() or None,
        "source_url": str(discovery.get("source_url") or article_url).strip() or None,
        "article_title": str(discovery.get("article_title") or "").strip(),
        "article_url": article_url,
        "description": str(discovery.get("description") or "").strip(),
        "signals": _jsonable(discovery.get("signals") or []),
        "confidence": int(discovery.get("confidence") or 0),
        "discovered_at": str(discovery.get("discovered_at") or "").strip() or None,
        "status": str(discovery.get("status") or "new").strip() or "new",
    }


def upsert_startup_discoveries(
    settings: Settings,
    discoveries: list[dict[str, Any]],
) -> int:
    if not database_enabled(settings):
        raise DatabaseUnavailable("NVIDIA_RADAR_DATABASE_URL nao configurado.")

    _psycopg, _dict_row, Jsonb = _import_psycopg()
    rows = [_discovery_row(discovery) for discovery in discoveries]
    rows = [
        row
        for row in rows
        if row["discovery_key"] and row["startup_key"] and row["startup_name"] and row["article_url"]
    ]
    if not rows:
        return 0

    added = 0
    with get_connection(settings) as connection:
        with connection.cursor() as cursor:
            for row in rows:
                cursor.execute(
                    """
                    SELECT discovery_key
                    FROM startup_discoveries
                    WHERE startup_key = %s
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    (row["startup_key"],),
                )
                existing = cursor.fetchone()
                if existing:
                    row["discovery_key"] = existing[0]

                cursor.execute(
                    """
                    INSERT INTO startup_discoveries (
                        discovery_key,
                        startup_key,
                        startup_name,
                        country_code,
                        sector,
                        stage,
                        source,
                        website_url,
                        github_url,
                        source_url,
                        article_title,
                        article_url,
                        description,
                        signals,
                        confidence,
                        discovered_at,
                        status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (discovery_key)
                    DO UPDATE SET
                        sector = EXCLUDED.sector,
                        stage = EXCLUDED.stage,
                        website_url = COALESCE(EXCLUDED.website_url, startup_discoveries.website_url),
                        github_url = COALESCE(EXCLUDED.github_url, startup_discoveries.github_url),
                        source_url = EXCLUDED.source_url,
                        article_title = EXCLUDED.article_title,
                        description = EXCLUDED.description,
                        signals = EXCLUDED.signals,
                        confidence = EXCLUDED.confidence,
                        discovered_at = COALESCE(EXCLUDED.discovered_at, startup_discoveries.discovered_at),
                        status = CASE
                            WHEN startup_discoveries.status IN (
                                'enriched',
                                'needs_website_review',
                                'manual_review'
                            )
                            AND EXCLUDED.status IN ('new', 'seen')
                            THEN startup_discoveries.status
                            ELSE EXCLUDED.status
                        END,
                        updated_at = now()
                    RETURNING (xmax = 0) AS inserted
                    """,
                    (
                        row["discovery_key"],
                        row["startup_key"],
                        row["startup_name"],
                        row["country_code"],
                        row["sector"],
                        row["stage"],
                        row["source"],
                        row["website_url"],
                        row["github_url"],
                        row["source_url"],
                        row["article_title"],
                        row["article_url"],
                        row["description"],
                        Jsonb(row["signals"]),
                        row["confidence"],
                        row["discovered_at"],
                        row["status"],
                    ),
                )
                if cursor.fetchone()[0]:
                    added += 1
    return added


def list_startup_discoveries(settings: Settings) -> list[dict[str, Any]]:
    if not database_enabled(settings):
        raise DatabaseUnavailable("NVIDIA_RADAR_DATABASE_URL nao configurado.")

    psycopg, dict_row, _Jsonb = _import_psycopg()
    with psycopg.connect(settings.database_url, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    startup_name,
                    country_code,
                    sector,
                    stage,
                    source,
                    website_url,
                    github_url,
                    source_url,
                    article_title,
                    article_url,
                    description,
                    signals,
                    confidence,
                    discovered_at::text AS discovered_at,
                    status
                FROM startup_discoveries
                ORDER BY created_at DESC, confidence DESC
                """
            )
            return list(cursor.fetchall())


def promote_startup_discoveries_to_catalog(
    settings: Settings,
    min_confidence: int = 50,
) -> dict[str, Any]:
    if not database_enabled(settings):
        raise DatabaseUnavailable("NVIDIA_RADAR_DATABASE_URL nao configurado.")

    discoveries = list_startup_discoveries(settings)
    current_names = {
        startup_key(candidate.get("startup_name"))
        for candidate in list_startup_catalog(settings)
    }
    imported = []
    skipped = []
    for discovery in discoveries:
        name_key = startup_key(discovery.get("startup_name"))
        if not name_key:
            skipped.append(discovery)
            continue
        if int(discovery.get("confidence") or 0) < min_confidence:
            skipped.append(discovery)
            continue

        candidate = {
            "startup_name": discovery["startup_name"],
            "country_code": discovery.get("country_code") or "BR",
            "sector": discovery.get("sector") or "unknown",
            "stage": discovery.get("stage"),
            "source": (
                f"enriched_{str(discovery.get('source') or 'news').replace('_news', '')}"
                if discovery.get("status") == "enriched"
                else f"discovered_{str(discovery.get('source') or 'news').replace('_news', '')}"
            ),
            "website_url": discovery.get("website_url"),
            "github_url": discovery.get("github_url"),
            "source_url": discovery.get("article_url") or discovery.get("source_url"),
            "description": discovery.get("description") or discovery.get("article_title"),
            "signals": discovery.get("signals") or ["noticia", "startupi", "Brasil"],
        }
        imported.append(candidate)
        current_names.add(name_key)

    if imported:
        upsert_startup_catalog(settings, imported)

    return {
        "imported": len(imported),
        "skipped": len(skipped),
        "total_active": startup_catalog_count(settings),
        "results": imported,
    }


def sync_nvidia_source_registry(
    settings: Settings,
    documents: list[dict[str, Any]],
) -> int:
    if not database_enabled(settings):
        raise DatabaseUnavailable("NVIDIA_RADAR_DATABASE_URL nao configurado.")

    rows = [
        {
            "product_name": str(document.get("product_name") or "").strip(),
            "category": str(document.get("category") or "unknown").strip(),
            "source_url": str(document.get("source_url") or "").strip(),
        }
        for document in documents
    ]
    rows = [row for row in rows if row["product_name"] and row["source_url"]]
    if not rows:
        return 0

    with get_connection(settings) as connection:
        with connection.cursor() as cursor:
            for row in rows:
                cursor.execute(
                    """
                    INSERT INTO nvidia_source_registry (
                        product_name,
                        category,
                        source_url
                    )
                    VALUES (%s, %s, %s)
                    ON CONFLICT (source_url)
                    DO UPDATE SET
                        product_name = EXCLUDED.product_name,
                        category = EXCLUDED.category,
                        is_active = true,
                        updated_at = now()
                    """,
                    (row["product_name"], row["category"], row["source_url"]),
                )
    return len(rows)


def list_nvidia_document_snapshots(settings: Settings) -> dict[str, dict[str, Any]]:
    if not database_enabled(settings):
        raise DatabaseUnavailable("NVIDIA_RADAR_DATABASE_URL nao configurado.")

    psycopg, dict_row, _Jsonb = _import_psycopg()
    with psycopg.connect(settings.database_url, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT ON (source_url)
                    source_url,
                    product_name,
                    category,
                    modified_at,
                    content_hash,
                    characters,
                    collected_at::text AS collected_at
                FROM nvidia_document_versions
                WHERE is_current = true
                ORDER BY source_url, collected_at DESC
                """
            )
            return {
                str(row["source_url"]): dict(row)
                for row in cursor.fetchall()
            }


def record_nvidia_document_versions(
    settings: Settings,
    sources: list[dict[str, Any]],
) -> int:
    if not database_enabled(settings):
        raise DatabaseUnavailable("NVIDIA_RADAR_DATABASE_URL nao configurado.")

    rows = [
        source
        for source in sources
        if source.get("source_url") and source.get("content_hash")
    ]
    if not rows:
        return 0

    with get_connection(settings) as connection:
        with connection.cursor() as cursor:
            for row in rows:
                cursor.execute(
                    """
                    UPDATE nvidia_document_versions
                    SET is_current = false
                    WHERE source_url = %s
                    """,
                    (str(row["source_url"]),),
                )
                cursor.execute(
                    """
                    INSERT INTO nvidia_document_versions (
                        source_url,
                        product_name,
                        category,
                        title,
                        modified_at,
                        content_hash,
                        characters,
                        collected_at,
                        is_current
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, COALESCE(%s::timestamptz, now()), true)
                    """,
                    (
                        str(row["source_url"]),
                        str(row.get("product_name") or ""),
                        str(row.get("category") or "unknown"),
                        str(row.get("title") or row.get("product_name") or ""),
                        row.get("modified_at"),
                        str(row["content_hash"]),
                        int(row.get("characters") or 0),
                        row.get("collected_at"),
                    ),
                )
    return len(rows)


def save_nvidia_update_checks(
    settings: Settings,
    checks: list[dict[str, Any]],
) -> int:
    if not database_enabled(settings):
        raise DatabaseUnavailable("NVIDIA_RADAR_DATABASE_URL nao configurado.")

    if not checks:
        return 0

    _psycopg, _dict_row, Jsonb = _import_psycopg()
    with get_connection(settings) as connection:
        with connection.cursor() as cursor:
            for check in checks:
                cursor.execute(
                    """
                    INSERT INTO nvidia_update_checks (
                        source_url,
                        product_name,
                        category,
                        checked_at,
                        local_content_hash,
                        remote_content_hash,
                        local_modified_at,
                        remote_modified_at,
                        status,
                        action,
                        is_useful_for_startups,
                        usefulness_score,
                        useful_topics,
                        usefulness_reason,
                        characters,
                        error_message
                    )
                    VALUES (%s, %s, %s, %s::timestamptz, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(check.get("source_url") or ""),
                        str(check.get("product_name") or ""),
                        str(check.get("category") or "unknown"),
                        check.get("checked_at"),
                        check.get("local_content_hash"),
                        check.get("remote_content_hash"),
                        check.get("local_modified_at"),
                        check.get("remote_modified_at"),
                        str(check.get("status") or "unknown"),
                        str(check.get("action") or "none"),
                        bool(check.get("is_useful_for_startups")),
                        int(check.get("usefulness_score") or 0),
                        Jsonb(_jsonable(check.get("useful_topics") or [])),
                        str(check.get("usefulness_reason") or ""),
                        int(check.get("characters") or 0),
                        check.get("error"),
                    ),
                )
    return len(checks)
