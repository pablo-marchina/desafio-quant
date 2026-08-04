ALTER TABLE evidence_checks
    ADD COLUMN IF NOT EXISTS severity TEXT NOT NULL DEFAULT 'info';

ALTER TABLE evidence_checks
    ADD COLUMN IF NOT EXISTS blocks_recommendation BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE evidence_checks
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;
