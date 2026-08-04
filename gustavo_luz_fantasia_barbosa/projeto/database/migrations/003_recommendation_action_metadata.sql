ALTER TABLE recommendations
    ADD COLUMN IF NOT EXISTS implementation_complexity TEXT NOT NULL DEFAULT 'medium';

ALTER TABLE recommendations
    ADD COLUMN IF NOT EXISTS next_action TEXT NOT NULL DEFAULT '';
