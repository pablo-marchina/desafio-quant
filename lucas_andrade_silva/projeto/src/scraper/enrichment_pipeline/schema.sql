CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS startup_ai_radar_catalog (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id TEXT NOT NULL UNIQUE,
    company_name TEXT NOT NULL,
    website TEXT,
    description TEXT,
    github_tentativas INTEGER NOT NULL DEFAULT 0,
    github_validacao_status TEXT NOT NULL DEFAULT 'nao_executado',
    technology_intelligence JSONB,
    nvidia_recommendation JSONB,
    competitive_analysis JSONB,
    action_report JSONB,
    ai_dependency_level TEXT NOT NULL DEFAULT 'INSUFFICIENT_EVIDENCE',
    enrichment_status TEXT NOT NULL DEFAULT 'needs_review',
    cnpj TEXT,
    cnpj_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    founding_year TEXT NOT NULL DEFAULT 'Not specified',
    location TEXT NOT NULL DEFAULT 'Brazil',
    ai_technology_focus TEXT NOT NULL DEFAULT 'Unknown',
    target_market TEXT,
    key_milestones TEXT,
    socios JSONB NOT NULL DEFAULT '[]'::jsonb,
    cnae TEXT,
    source_url TEXT,
    validation_status TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE startup_ai_radar_catalog ADD COLUMN IF NOT EXISTS candidate_id TEXT;
ALTER TABLE startup_ai_radar_catalog ADD COLUMN IF NOT EXISTS github_tentativas INTEGER NOT NULL DEFAULT 0;
ALTER TABLE startup_ai_radar_catalog ADD COLUMN IF NOT EXISTS github_validacao_status TEXT NOT NULL DEFAULT 'nao_executado';
ALTER TABLE startup_ai_radar_catalog ADD COLUMN IF NOT EXISTS technology_intelligence JSONB;
ALTER TABLE startup_ai_radar_catalog ADD COLUMN IF NOT EXISTS nvidia_recommendation JSONB;
ALTER TABLE startup_ai_radar_catalog ADD COLUMN IF NOT EXISTS competitive_analysis JSONB;
ALTER TABLE startup_ai_radar_catalog ADD COLUMN IF NOT EXISTS action_report JSONB;
ALTER TABLE startup_ai_radar_catalog ADD COLUMN IF NOT EXISTS ai_dependency_level TEXT NOT NULL DEFAULT 'INSUFFICIENT_EVIDENCE';
ALTER TABLE startup_ai_radar_catalog ADD COLUMN IF NOT EXISTS enrichment_status TEXT NOT NULL DEFAULT 'needs_review';
ALTER TABLE startup_ai_radar_catalog ADD COLUMN IF NOT EXISTS cnpj TEXT;
ALTER TABLE startup_ai_radar_catalog ADD COLUMN IF NOT EXISTS cnpj_data JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE startup_ai_radar_catalog ADD COLUMN IF NOT EXISTS socios JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE startup_ai_radar_catalog ADD COLUMN IF NOT EXISTS cnae TEXT;
ALTER TABLE startup_ai_radar_catalog ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE startup_ai_radar_catalog ADD COLUMN IF NOT EXISTS razao_social TEXT;
ALTER TABLE startup_ai_radar_catalog ADD COLUMN IF NOT EXISTS nome_fantasia TEXT;
ALTER TABLE startup_ai_radar_catalog ADD COLUMN IF NOT EXISTS municipio TEXT;
ALTER TABLE startup_ai_radar_catalog ADD COLUMN IF NOT EXISTS estado TEXT;
ALTER TABLE startup_ai_radar_catalog ADD COLUMN IF NOT EXISTS cep TEXT;
ALTER TABLE startup_ai_radar_catalog ADD COLUMN IF NOT EXISTS logradouro TEXT;
ALTER TABLE startup_ai_radar_catalog ADD COLUMN IF NOT EXISTS bairro TEXT;
ALTER TABLE startup_ai_radar_catalog ADD COLUMN IF NOT EXISTS natureza_juridica TEXT;
ALTER TABLE startup_ai_radar_catalog ADD COLUMN IF NOT EXISTS porte TEXT;
ALTER TABLE startup_ai_radar_catalog ADD COLUMN IF NOT EXISTS capital_social NUMERIC(18, 2);
ALTER TABLE startup_ai_radar_catalog ADD COLUMN IF NOT EXISTS situacao_cadastral TEXT;
ALTER TABLE startup_ai_radar_catalog ADD COLUMN IF NOT EXISTS data_abertura TEXT;
ALTER TABLE startup_ai_radar_catalog ADD COLUMN IF NOT EXISTS inscricao_estadual TEXT;
ALTER TABLE startup_ai_radar_catalog ADD COLUMN IF NOT EXISTS cnae_principal TEXT;
ALTER TABLE startup_ai_radar_catalog ADD COLUMN IF NOT EXISTS cnae_secundarias JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE startup_ai_radar_catalog ALTER COLUMN founding_year DROP NOT NULL;
ALTER TABLE startup_ai_radar_catalog ALTER COLUMN location DROP NOT NULL;
ALTER TABLE startup_ai_radar_catalog ALTER COLUMN ai_technology_focus DROP NOT NULL;
ALTER TABLE startup_ai_radar_catalog ALTER COLUMN company_name DROP NOT NULL;
ALTER TABLE startup_ai_radar_catalog ALTER COLUMN socios DROP NOT NULL;
ALTER TABLE startup_ai_radar_catalog ALTER COLUMN cnae_secundarias DROP NOT NULL;

UPDATE startup_ai_radar_catalog
SET candidate_id = id::text
WHERE candidate_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS startup_ai_radar_catalog_candidate_id_uidx
    ON startup_ai_radar_catalog (candidate_id);

CREATE INDEX IF NOT EXISTS startup_ai_radar_catalog_company_name_idx
    ON startup_ai_radar_catalog (LOWER(company_name));
CREATE INDEX IF NOT EXISTS startup_ai_radar_catalog_status_idx
    ON startup_ai_radar_catalog (validation_status);
CREATE INDEX IF NOT EXISTS startup_ai_radar_catalog_enrichment_status_idx
    ON startup_ai_radar_catalog (enrichment_status);

DO $$
DECLARE
    constraint_name TEXT;
BEGIN
    FOR constraint_name IN
        SELECT tc.constraint_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.check_constraints AS cc
          ON cc.constraint_name = tc.constraint_name
        WHERE tc.table_schema = 'public'
          AND tc.table_name = 'startup_ai_radar_catalog'
          AND tc.constraint_type = 'CHECK'
          AND cc.check_clause ILIKE '%validation_status%'
    LOOP
        EXECUTE format(
            'ALTER TABLE startup_ai_radar_catalog DROP CONSTRAINT %I',
            constraint_name
        );
    END LOOP;
END $$;

CREATE TABLE IF NOT EXISTS github_repository_validations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id TEXT NOT NULL,
    github_repo_url TEXT NOT NULL,
    criterios_atendidos TEXT[] NOT NULL DEFAULT '{}',
    evidencia TEXT,
    data_validacao TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (empresa_id, github_repo_url)
);

CREATE INDEX IF NOT EXISTS github_repository_validations_empresa_id_idx
    ON github_repository_validations (empresa_id);
