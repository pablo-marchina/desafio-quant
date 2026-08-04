-- Fase 1 - Scraper 1 (Discovery): tabela de startups descobertas.
-- Idempotente: pode rodar varias vezes sem efeito colateral.

CREATE TABLE IF NOT EXISTS startups_discovered (
    id               SERIAL PRIMARY KEY,
    name             VARCHAR(255) NOT NULL,
    sector           VARCHAR(150),
    official_website TEXT,
    source_name      VARCHAR(100) NOT NULL,
    source_url       TEXT,
    status           VARCHAR(50) DEFAULT 'pending_deep_scan',
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Unicidade NULL-safe sobre (nome, site) normalizados.
-- IMPORTANTE: no PostgreSQL multiplos NULL NAO disparam conflito de unicidade
-- por padrao. Por isso o indice usa COALESCE(official_website, '') -- e a clausula
-- ON CONFLICT na aplicacao precisa usar exatamente a mesma expressao -- garantindo
-- que duas startups com mesmo nome e site nulo colidam, em vez de duplicarem.
CREATE UNIQUE INDEX IF NOT EXISTS uq_startup_identity
    ON startups_discovered (lower(trim(name)), coalesce(lower(official_website), ''));

-- Acesso rapido por status (ex.: listar high_priority para o deep scan da Fase 2).
CREATE INDEX IF NOT EXISTS ix_startup_status ON startups_discovered (status);
