-- =====================================================================
-- NVISION — Schema PostgreSQL (dados estruturados de startups)
-- Baseado em ux.md §7.6. Aplicado automaticamente pelo docker-compose
-- na primeira subida do container Postgres.
--
-- A modelagem completa evolui ao longo das semanas; este é o ponto de
-- partida com as tabelas centrais do pipeline.
-- =====================================================================

-- Startups identificadas e classificadas pelo radar
CREATE TABLE IF NOT EXISTS startups (
    id             SERIAL PRIMARY KEY,
    name           TEXT NOT NULL UNIQUE,  -- chave natural: permite UPSERT por nome
    sector         TEXT,
    stage          TEXT,                 -- ex.: seed, série A...
    funding        TEXT,                 -- texto livre (ex.: "R$ 12M")
    classification TEXT,                 -- AI-native | AI-enabled | Non-AI
    confidence     NUMERIC(4,3),         -- 0.000 a 1.000
    fit_score      INTEGER,              -- 0 a 100
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Detalhe da qualificação (alimenta o dropdown da página Qualificadas).
-- ADD COLUMN IF NOT EXISTS torna a migração idempotente: bancos já criados
-- ganham as colunas na próxima aplicação do schema, sem recriar a tabela.
ALTER TABLE startups ADD COLUMN IF NOT EXISTS description     TEXT;   -- sobre a empresa
ALTER TABLE startups ADD COLUMN IF NOT EXISTS recommendations JSONB;  -- produtos NVIDIA + fit
ALTER TABLE startups ADD COLUMN IF NOT EXISTS briefing        TEXT;   -- briefing executivo (markdown)

-- Funil de qualificação (Kanban — página Qualificadas)
CREATE TABLE IF NOT EXISTS pipeline_stages (
    id          SERIAL PRIMARY KEY,
    startup_id  INTEGER NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
    stage       TEXT NOT NULL,           -- identificadas, contatadas, demo...
    notes       TEXT,
    advanced_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    advanced_by TEXT
);

-- Execuções de pipeline (uma por disparo do gestor)
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id           SERIAL PRIMARY KEY,
    query        TEXT NOT NULL,
    params_json  JSONB,
    status       TEXT NOT NULL DEFAULT 'running',  -- running|done|error
    started_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

-- Log estruturado por agente (alimenta o live log do frontend)
CREATE TABLE IF NOT EXISTS pipeline_logs (
    id         SERIAL PRIMARY KEY,
    run_id     INTEGER NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    agent_name TEXT NOT NULL,
    level      TEXT NOT NULL DEFAULT 'info',  -- info|ok|warning|error
    message    TEXT NOT NULL,
    timestamp  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Índices para as consultas mais comuns
CREATE INDEX IF NOT EXISTS idx_stages_startup  ON pipeline_stages(startup_id);
CREATE INDEX IF NOT EXISTS idx_logs_run        ON pipeline_logs(run_id);
