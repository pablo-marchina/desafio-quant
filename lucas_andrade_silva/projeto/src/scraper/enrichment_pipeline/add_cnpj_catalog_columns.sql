-- Colunas usadas pelo fluxo Brasil.io -> BrasilAPI -> Groq.
ALTER TABLE startup_ai_radar_catalog
    ADD COLUMN IF NOT EXISTS cnpj TEXT,
    ADD COLUMN IF NOT EXISTS cnae TEXT,
    ADD COLUMN IF NOT EXISTS socios JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS cnpj_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS razao_social TEXT,
    ADD COLUMN IF NOT EXISTS nome_fantasia TEXT,
    ADD COLUMN IF NOT EXISTS municipio TEXT,
    ADD COLUMN IF NOT EXISTS estado TEXT,
    ADD COLUMN IF NOT EXISTS cep TEXT,
    ADD COLUMN IF NOT EXISTS logradouro TEXT,
    ADD COLUMN IF NOT EXISTS bairro TEXT,
    ADD COLUMN IF NOT EXISTS natureza_juridica TEXT,
    ADD COLUMN IF NOT EXISTS porte TEXT,
    ADD COLUMN IF NOT EXISTS capital_social NUMERIC(18, 2),
    ADD COLUMN IF NOT EXISTS situacao_cadastral TEXT,
    ADD COLUMN IF NOT EXISTS data_abertura TEXT,
    ADD COLUMN IF NOT EXISTS inscricao_estadual TEXT,
    ADD COLUMN IF NOT EXISTS cnae_principal TEXT,
    ADD COLUMN IF NOT EXISTS cnae_secundarias JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE startup_ai_radar_catalog
    ALTER COLUMN founding_year DROP NOT NULL,
    ALTER COLUMN location DROP NOT NULL,
    ALTER COLUMN ai_technology_focus DROP NOT NULL,
    ALTER COLUMN company_name DROP NOT NULL,
    ALTER COLUMN socios DROP NOT NULL,
    ALTER COLUMN cnae_secundarias DROP NOT NULL;

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

CREATE INDEX IF NOT EXISTS startup_ai_radar_catalog_cnpj_idx
    ON startup_ai_radar_catalog (cnpj)
    WHERE cnpj IS NOT NULL;
