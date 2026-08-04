CREATE TABLE IF NOT EXISTS briefings (
    id              SERIAL PRIMARY KEY,
    startup_id      INTEGER NOT NULL REFERENCES startups_discovered(id) ON DELETE CASCADE,
    report_markdown TEXT NOT NULL,
    generated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (startup_id)
);
