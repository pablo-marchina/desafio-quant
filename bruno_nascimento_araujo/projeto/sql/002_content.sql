-- Fase 2 - Scraper 2 (Deep Extraction): chunks de conteudo por startup.
-- Idempotente: pode rodar varias vezes sem efeito colateral.

CREATE TABLE IF NOT EXISTS startups_content (
    id             SERIAL PRIMARY KEY,
    startup_id     INTEGER NOT NULL REFERENCES startups_discovered(id) ON DELETE CASCADE,
    -- chunk_type values: 'main_text' | 'use_case' | 'tech_stack' | 'founders' | 'funding'
    chunk_type     VARCHAR(50) NOT NULL,
    content        TEXT NOT NULL,
    source_url     TEXT NOT NULL,
    has_ai_signals BOOLEAN DEFAULT FALSE,
    collected_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Leitura por startup (join para RAG / Evidence Validator Agent).
CREATE INDEX IF NOT EXISTS ix_content_startup_id
    ON startups_content (startup_id);

-- Filtro rapido por sinal AI (Fase 3 - ranking).
CREATE INDEX IF NOT EXISTS ix_content_ai_signals
    ON startups_content (has_ai_signals)
    WHERE has_ai_signals = TRUE;
