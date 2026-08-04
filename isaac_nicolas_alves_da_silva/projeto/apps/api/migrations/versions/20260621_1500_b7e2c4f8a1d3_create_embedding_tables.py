"""create embedding tables

Revision ID: b7e2c4f8a1d3
Revises: 3f8d1e2a9c7b
Create Date: 2026-06-21 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "b7e2c4f8a1d3"
down_revision: str | None = "3f8d1e2a9c7b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "embedding_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("total_chunks", sa.Integer(), nullable=False),
        sa.Column("succeeded_chunks", sa.Integer(), nullable=False),
        sa.Column("failed_chunks", sa.Integer(), nullable=False),
        sa.Column("total_latency_ms", sa.Integer(), nullable=False),
        sa.Column("total_input_char_count", sa.Integer(), nullable=False),
        sa.Column("total_estimated_input_tokens", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_embedding_jobs_document_id", "embedding_jobs", ["document_id"]
    )

    op.create_table(
        "embedding_job_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("vector_dimension", sa.Integer(), nullable=True),
        sa.Column("input_char_count", sa.Integer(), nullable=True),
        sa.Column("estimated_input_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["embedding_jobs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            ["chunks.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_embedding_job_chunks_job_id", "embedding_job_chunks", ["job_id"]
    )
    op.create_index(
        "ix_embedding_job_chunks_chunk_id", "embedding_job_chunks", ["chunk_id"]
    )
    op.create_index(
        "ix_embedding_job_chunks_status", "embedding_job_chunks", ["status"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_embedding_job_chunks_status", table_name="embedding_job_chunks"
    )
    op.drop_index(
        "ix_embedding_job_chunks_chunk_id", table_name="embedding_job_chunks"
    )
    op.drop_index(
        "ix_embedding_job_chunks_job_id", table_name="embedding_job_chunks"
    )
    op.drop_table("embedding_job_chunks")

    op.drop_index("ix_embedding_jobs_document_id", table_name="embedding_jobs")
    op.drop_table("embedding_jobs")
