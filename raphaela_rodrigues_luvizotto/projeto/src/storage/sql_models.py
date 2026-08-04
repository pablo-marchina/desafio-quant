from __future__ import annotations

from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class StartupRecord(Base):
    __tablename__ = "startups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    canonical_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    segment: Mapped[str | None] = mapped_column(String(255), nullable=True)
    short_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ai_native_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    classification_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    classification_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    source_urls: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    metadata_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[str] = mapped_column(String(64))
    updated_at: Mapped[str] = mapped_column(String(64))


class EvidenceRecord(Base):
    __tablename__ = "evidences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    startup_name: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(120))
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    collected_at: Mapped[str] = mapped_column(String(64))
    method: Mapped[str] = mapped_column(String(120))
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_validated: Mapped[bool] = mapped_column(Boolean, default=False)
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ScrapeRunRecord(Base):
    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    query: Mapped[str] = mapped_column(Text, index=True)
    startup_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(80))
    urls_requested: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    documents_collected: Mapped[int] = mapped_column(Integer, default=0)
    raw_artifact_dir: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[str] = mapped_column(String(64))
    finished_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    errors: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    metadata_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class RecommendationRecord(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    startup_name: Mapped[str] = mapped_column(String(255), index=True)
    recommendation_type: Mapped[str] = mapped_column(String(120))
    summary: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str] = mapped_column(Text)
    matched_products: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    matched_context_snippets: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    next_steps: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    metadata_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
