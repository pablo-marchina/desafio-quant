CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE TABLE IF NOT EXISTS validated_startup_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_company_id TEXT,
    company_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    source_name TEXT,
    source_url TEXT,
    is_valid_company BOOLEAN,
    is_brazilian BOOLEAN,
    is_startup BOOLEAN,
    uses_ai_potentially BOOLEAN,
    ai_classification TEXT NOT NULL DEFAULT 'NON_AI'
        CHECK (ai_classification IN ('AI_NATIVE','AI_ENABLED','NON_AI')),
    foundation_year INTEGER,
    priority TEXT NOT NULL DEFAULT 'REVIEW'
        CHECK (priority IN ('HIGH','MEDIUM','LOW','REVIEW')),
    validation_status TEXT NOT NULL DEFAULT 'REVIEW'
        CHECK (validation_status IN ('APPROVED','REVIEW','REJECTED','DISCARDED')),
    rejection_reason TEXT,
    evidence_text TEXT,
    evidence_urls TEXT[] NOT NULL DEFAULT '{}',
    website_url TEXT,
    linkedin_url TEXT,
    cnpj TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    discard_reason TEXT,
    llm_confidence TEXT CHECK (llm_confidence IN ('H','M','L')),
    weight_contributions JSONB NOT NULL DEFAULT '{}'::jsonb,
    confidence_score INTEGER NOT NULL CHECK (confidence_score BETWEEN 0 AND 100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS validated_startup_candidates_normalized_name_uidx
    ON validated_startup_candidates (normalized_name);
ALTER TABLE validated_startup_candidates ADD COLUMN IF NOT EXISTS website_url TEXT;
ALTER TABLE validated_startup_candidates ADD COLUMN IF NOT EXISTS linkedin_url TEXT;
ALTER TABLE validated_startup_candidates ADD COLUMN IF NOT EXISTS cnpj TEXT;
ALTER TABLE validated_startup_candidates ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE validated_startup_candidates ADD COLUMN IF NOT EXISTS discard_reason TEXT;
ALTER TABLE validated_startup_candidates ADD COLUMN IF NOT EXISTS llm_confidence TEXT;
ALTER TABLE validated_startup_candidates ADD COLUMN IF NOT EXISTS weight_contributions JSONB NOT NULL DEFAULT '{}'::jsonb;
