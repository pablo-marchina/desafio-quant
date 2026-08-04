ALTER TABLE scraped_pages
    ADD COLUMN IF NOT EXISTS title TEXT;

ALTER TABLE scraped_pages
    ADD COLUMN IF NOT EXISTS source_type TEXT NOT NULL DEFAULT 'startup_page';

ALTER TABLE scraped_pages
    ADD COLUMN IF NOT EXISTS collected_at TEXT;
