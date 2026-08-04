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
