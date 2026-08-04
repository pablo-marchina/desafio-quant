"""initial schema matching init_db()

Revision ID: 0001
Revises:
Create Date: 2026-06-22
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS startups (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            sector TEXT,
            product TEXT,
            description TEXT,
            founders TEXT DEFAULT '[]',
            customers TEXT DEFAULT '[]',
            funding TEXT,
            cited_technologies TEXT DEFAULT '[]',
            ai_usage_summary TEXT,
            classification_label TEXT,
            classification_confidence REAL,
            classification_rationale TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL,
            startup_id TEXT REFERENCES startups(id),
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            completed_at TEXT
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS source_documents (
            id TEXT PRIMARY KEY,
            run_id INTEGER NOT NULL REFERENCES runs(id),
            url TEXT NOT NULL,
            domain TEXT NOT NULL,
            source_type TEXT NOT NULL,
            title TEXT,
            text TEXT NOT NULL,
            retrieved_at TEXT NOT NULL,
            collection_method TEXT NOT NULL
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS evidence_claims (
            id TEXT PRIMARY KEY,
            run_id INTEGER NOT NULL REFERENCES runs(id),
            source_document_id TEXT NOT NULL REFERENCES source_documents(id),
            text TEXT NOT NULL,
            claim_type TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0.0
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS validations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL REFERENCES runs(id),
            has_minimum_evidence INTEGER NOT NULL DEFAULT 0,
            source_quality TEXT NOT NULL DEFAULT 'weak',
            supporting_evidence_ids TEXT DEFAULT '[]',
            conflicts TEXT DEFAULT '[]',
            caveats TEXT DEFAULT '[]',
            requires_human_review INTEGER NOT NULL DEFAULT 0
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS recommendations (
            id TEXT PRIMARY KEY,
            run_id INTEGER NOT NULL REFERENCES runs(id),
            technology TEXT NOT NULL,
            target_gap TEXT NOT NULL,
            technical_justification TEXT NOT NULL,
            business_justification TEXT NOT NULL,
            priority TEXT NOT NULL DEFAULT 'medium',
            implementation_complexity TEXT NOT NULL DEFAULT 'medium',
            suggested_next_action TEXT NOT NULL,
            startup_evidence_ids TEXT DEFAULT '[]',
            nvidia_knowledge_ids TEXT DEFAULT '[]'
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS recommendations")
    op.execute("DROP TABLE IF EXISTS validations")
    op.execute("DROP TABLE IF EXISTS evidence_claims")
    op.execute("DROP TABLE IF EXISTS source_documents")
    op.execute("DROP TABLE IF EXISTS runs")
    op.execute("DROP TABLE IF EXISTS startups")
