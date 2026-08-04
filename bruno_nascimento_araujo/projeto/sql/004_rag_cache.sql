CREATE TABLE IF NOT EXISTS nvidia_rag_cache (
    id              SERIAL PRIMARY KEY,
    startup_id      INT REFERENCES startups_discovered(id) ON DELETE CASCADE,
    query           TEXT NOT NULL,
    recommendations JSONB NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_rag_cache_startup ON nvidia_rag_cache (startup_id);
