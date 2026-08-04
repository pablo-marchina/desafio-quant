-- Tabela de classificacoes das startups (Fase 3 - Classifier Agent)
CREATE TABLE IF NOT EXISTS classifications (
    id                   SERIAL PRIMARY KEY,
    startup_id           INTEGER NOT NULL REFERENCES startups_discovered(id) ON DELETE CASCADE,
    classification       VARCHAR(20) NOT NULL CHECK (classification IN ('ai_native', 'ai_enabled', 'non_ai')),
    confidence_score     FLOAT NOT NULL,
    justification        TEXT NOT NULL,
    evidence_chunks      TEXT[] NOT NULL,
    provider_used        VARCHAR(50) NOT NULL,
    classification_date  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (startup_id)
);

CREATE INDEX IF NOT EXISTS idx_classifications_classification ON classifications (classification);
CREATE INDEX IF NOT EXISTS idx_classifications_provider      ON classifications (provider_used);
