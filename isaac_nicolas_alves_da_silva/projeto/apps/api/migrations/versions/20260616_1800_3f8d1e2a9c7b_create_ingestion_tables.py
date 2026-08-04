"""create ingestion tables

Revision ID: 3f8d1e2a9c7b
Revises: 9e1f3b5c8a2d
Create Date: 2026-06-16 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "3f8d1e2a9c7b"
down_revision: str | None = "9e1f3b5c8a2d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ingestion_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scraping_result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["scraping_result_id"],
            ["scraping_results.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ingestion_jobs_scraping_result_id",
        "ingestion_jobs",
        ["scraping_result_id"],
    )
    op.create_index("ix_ingestion_jobs_status", "ingestion_jobs", ["status"])

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ingestion_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scraping_result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("clean_text", sa.Text(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["ingestion_job_id"],
            ["ingestion_jobs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ingestion_job_id", name="uq_documents_ingestion_job_id"),
    )
    op.create_index(
        "ix_documents_scraping_result_id",
        "documents",
        ["scraping_result_id"],
    )

    op.create_table(
        "chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    op.create_index("ix_chunks_chunk_index", "chunks", ["chunk_index"])


def downgrade() -> None:
    op.drop_index("ix_chunks_chunk_index", table_name="chunks")
    op.drop_index("ix_chunks_document_id", table_name="chunks")
    op.drop_table("chunks")

    op.drop_index("ix_documents_scraping_result_id", table_name="documents")
    op.drop_table("documents")

    op.drop_index("ix_ingestion_jobs_status", table_name="ingestion_jobs")
    op.drop_index(
        "ix_ingestion_jobs_scraping_result_id", table_name="ingestion_jobs"
    )
    op.drop_table("ingestion_jobs")
