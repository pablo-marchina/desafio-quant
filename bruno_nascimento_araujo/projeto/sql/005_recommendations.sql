CREATE TABLE IF NOT EXISTS recommendations (
    id                    SERIAL PRIMARY KEY,
    startup_id            INTEGER NOT NULL REFERENCES startups_discovered(id) ON DELETE CASCADE,
    classification        VARCHAR(20) NOT NULL,
    heuristic_suggestions TEXT,
    recommendations       JSONB NOT NULL,
    generated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (startup_id)
);
