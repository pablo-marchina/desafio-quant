"""Transactional product models for the NVIDIA Startup AI Radar."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class Startup(TimestampMixin, Base):
    __tablename__ = "startups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    website: Mapped[str] = mapped_column(String(2048), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False, default="Brazil")
    sector: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    product_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active", index=True)
    tags_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    evidence: Mapped[list[StartupEvidence]] = relationship(back_populates="startup", cascade="all, delete-orphan")
    analysis_runs: Mapped[list[AnalysisRun]] = relationship(back_populates="startup", cascade="all, delete-orphan")


class StartupEvidence(TimestampMixin, Base):
    __tablename__ = "startup_evidence"
    __table_args__ = (Index("ix_startup_evidence_startup_collected", "startup_id", "collected_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    startup_id: Mapped[str] = mapped_column(ForeignKey("startups.id", ondelete="CASCADE"), nullable=False, index=True)
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    quote_or_evidence: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    evidence_kind: Mapped[str] = mapped_column(String(50), nullable=False, default="unverified", index=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    startup: Mapped[Startup] = relationship(back_populates="evidence")


class AnalysisRun(TimestampMixin, Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (Index("ix_analysis_runs_startup_created", "startup_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    startup_id: Mapped[str] = mapped_column(ForeignKey("startups.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="queued", index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    degraded_reason: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    input_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    output_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    pipeline_version: Mapped[str] = mapped_column(String(100), nullable=False, default="current")
    corpus_version: Mapped[str | None] = mapped_column(String(100))
    config_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    startup: Mapped[Startup] = relationship(back_populates="analysis_runs")
    scores: Mapped[list[ScoreRecord]] = relationship(back_populates="analysis_run", cascade="all, delete-orphan")
    gaps: Mapped[list[GapDiagnosisRecord]] = relationship(back_populates="analysis_run", cascade="all, delete-orphan")
    mappings: Mapped[list[NvidiaMappingRecord]] = relationship(
        back_populates="analysis_run", cascade="all, delete-orphan"
    )
    briefs: Mapped[list[ActionBriefRecord]] = relationship(back_populates="analysis_run", cascade="all, delete-orphan")
    readiness_checks: Mapped[list[ProductReadinessCheck]] = relationship(
        back_populates="analysis_run", cascade="all, delete-orphan"
    )
    reviews: Mapped[list[ReviewDecision]] = relationship(back_populates="analysis_run", cascade="all, delete-orphan")
    exports: Mapped[list[ExportRecord]] = relationship(back_populates="analysis_run", cascade="all, delete-orphan")
    activation_recommendations: Mapped[list[ActivationRecommendationRecord]] = relationship(
        back_populates="analysis_run", cascade="all, delete-orphan"
    )
    dossiers: Mapped[list[ActivationDossierRecord]] = relationship(
        back_populates="analysis_run", cascade="all, delete-orphan"
    )
    quality_runs: Mapped[list[ProductQualityRun]] = relationship(
        back_populates="analysis_run", cascade="all, delete-orphan"
    )
    opportunity_scores: Mapped[list[OpportunityScoreRecord]] = relationship(
        back_populates="analysis_run", cascade="all, delete-orphan"
    )


class ScoreRecord(TimestampMixin, Base):
    __tablename__ = "score_records"
    __table_args__ = (UniqueConstraint("analysis_run_id", "score_type", name="uq_run_score_type"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    score_type: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    components_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    missing_evidence_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    analysis_run: Mapped[AnalysisRun] = relationship(back_populates="scores")


class GapDiagnosisRecord(TimestampMixin, Base):
    __tablename__ = "gap_diagnosis_records"
    __table_args__ = (UniqueConstraint("analysis_run_id", "gap_type", name="uq_run_gap_type"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    gap_type: Mapped[str] = mapped_column(String(100), nullable=False)
    detected: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    evidence_tag: Mapped[str] = mapped_column(String(50), nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence_refs_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    missing_evidence_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    analysis_run: Mapped[AnalysisRun] = relationship(back_populates="gaps")
    mappings: Mapped[list[NvidiaMappingRecord]] = relationship(back_populates="gap_record")


class NvidiaMappingRecord(TimestampMixin, Base):
    __tablename__ = "nvidia_mapping_records"
    __table_args__ = (
        Index(
            "ix_nvidia_mapping_run_gap_technology",
            "analysis_run_id",
            "addresses_gap",
            "technology_name",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    gap_record_id: Mapped[str | None] = mapped_column(
        ForeignKey("gap_diagnosis_records.id", ondelete="SET NULL"), index=True
    )
    technology_name: Mapped[str] = mapped_column(String(255), nullable=False)
    addresses_gap: Mapped[str] = mapped_column(String(100), nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False, default="")
    recommendation_action: Mapped[str | None] = mapped_column(String(50))
    priority: Mapped[str | None] = mapped_column(String(20))
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    analysis_run: Mapped[AnalysisRun] = relationship(back_populates="mappings")
    gap_record: Mapped[GapDiagnosisRecord | None] = relationship(back_populates="mappings")


class ActionBriefRecord(TimestampMixin, Base):
    __tablename__ = "action_brief_records"
    __table_args__ = (
        UniqueConstraint("analysis_run_id", "version", name="uq_run_brief_version"),
        Index("ix_action_brief_run_latest", "analysis_run_id", "is_latest"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    schema_version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0")
    brief_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    brief_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    is_latest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    analysis_run: Mapped[AnalysisRun] = relationship(back_populates="briefs")


class ProductReadinessCheck(TimestampMixin, Base):
    __tablename__ = "product_readiness_checks"
    __table_args__ = (
        Index("ix_readiness_run_code", "analysis_run_id", "code"),
        Index("ix_readiness_status_observed", "status", "observed_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    analysis_run_id: Mapped[str | None] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    internal_detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False, default="")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    analysis_run: Mapped[AnalysisRun | None] = relationship(back_populates="readiness_checks")


class ReviewDecision(TimestampMixin, Base):
    __tablename__ = "review_decisions"
    __table_args__ = (Index("ix_review_run_created", "analysis_run_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    startup_id: Mapped[str] = mapped_column(ForeignKey("startups.id", ondelete="CASCADE"), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(50), nullable=False)
    reviewer: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    thread_id: Mapped[str | None] = mapped_column(String(255), index=True)
    review_payload_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status_before_resume: Mapped[str | None] = mapped_column(String(50))
    status_after_resume: Mapped[str | None] = mapped_column(String(50))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    analysis_run: Mapped[AnalysisRun] = relationship(back_populates="reviews")
    startup: Mapped[Startup] = relationship()


class ExportRecord(TimestampMixin, Base):
    __tablename__ = "export_records"
    __table_args__ = (Index("ix_export_run_type", "analysis_run_id", "export_type"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action_brief_id: Mapped[str | None] = mapped_column(ForeignKey("action_brief_records.id", ondelete="SET NULL"))
    export_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    storage_path: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    error_message: Mapped[str | None] = mapped_column(Text)

    analysis_run: Mapped[AnalysisRun] = relationship(back_populates="exports")
    action_brief: Mapped[ActionBriefRecord | None] = relationship()


class ClaimRecord(TimestampMixin, Base):
    __tablename__ = "claim_records"
    __table_args__ = (
        Index("ix_claim_startup_type", "startup_id", "claim_type"),
        Index("ix_claim_run_review", "analysis_run_id", "review_status"),
        Index("ix_claim_support", "support_level"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    startup_id: Mapped[str] = mapped_column(ForeignKey("startups.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    support_level: Mapped[str] = mapped_column(String(20), nullable=False, default="unsupported")
    confidence: Mapped[str] = mapped_column(String(20), nullable=False, default="low")
    evidence_refs_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    used_in_score: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    used_in_gap: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    used_in_mapping: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    used_in_brief: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    review_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unreviewed")
    reviewer_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    startup: Mapped[Startup] = relationship()
    analysis_run: Mapped[AnalysisRun] = relationship()


class ActivationRecommendationRecord(TimestampMixin, Base):
    __tablename__ = "activation_recommendations"
    __table_args__ = (
        Index("ix_activation_run_id", "analysis_run_id"),
        Index("ix_activation_playbook_id", "playbook_id"),
        Index("ix_activation_recommended_motion", "recommended_motion"),
        Index("ix_activation_priority", "priority"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    playbook_id: Mapped[str] = mapped_column(String(100), nullable=False)
    playbook_name: Mapped[str] = mapped_column(String(255), nullable=False)
    matched_gap_types_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    matched_claim_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    nvidia_technologies_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    technical_experiment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    success_metrics_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    recommended_motion: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False, default="low")
    reasoning: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence_refs_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    risks_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    next_step: Mapped[str] = mapped_column(Text, nullable=False, default="")

    analysis_run: Mapped[AnalysisRun] = relationship(back_populates="activation_recommendations")


class ActivationDossierRecord(TimestampMixin, Base):
    __tablename__ = "activation_dossier_records"
    __table_args__ = (
        UniqueConstraint("analysis_run_id", "version", name="uq_run_dossier_version"),
        Index("ix_dossier_run_latest", "analysis_run_id", "is_latest"),
        Index("ix_dossier_recommended_motion", "recommended_motion"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    schema_version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0")
    dossier_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    dossier_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    is_latest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    evidence_coverage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    unsupported_claim_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    top_activation_playbook_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    recommended_motion: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    review_status: Mapped[str | None] = mapped_column(String(50), nullable=True)

    analysis_run: Mapped[AnalysisRun] = relationship(back_populates="dossiers")


class ProductQualityRun(TimestampMixin, Base):
    __tablename__ = "product_quality_runs"
    __table_args__ = (
        Index("ix_quality_run_analysis", "analysis_run_id"),
        Index("ix_quality_run_status", "status"),
        Index("ix_quality_run_created", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dossier_id: Mapped[str | None] = mapped_column(
        ForeignKey("activation_dossier_records.id", ondelete="SET NULL"), nullable=True
    )
    action_brief_id: Mapped[str | None] = mapped_column(
        ForeignKey("action_brief_records.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evaluator_version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0")
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    degraded_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    analysis_run: Mapped[AnalysisRun] = relationship(back_populates="quality_runs")
    dossier: Mapped[ActivationDossierRecord | None] = relationship()
    action_brief: Mapped[ActionBriefRecord | None] = relationship()
    metrics: Mapped[list[ProductQualityMetric]] = relationship(
        back_populates="quality_run", cascade="all, delete-orphan"
    )


class ProductQualityMetric(TimestampMixin, Base):
    __tablename__ = "product_quality_metrics"
    __table_args__ = (
        Index("ix_quality_metric_run", "quality_run_id"),
        Index("ix_quality_metric_name", "metric_name"),
        Index("ix_quality_metric_passed", "passed"),
        Index("ix_quality_metric_severity", "severity"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    quality_run_id: Mapped[str] = mapped_column(
        ForeignKey("product_quality_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="warn")
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    quality_run: Mapped[ProductQualityRun] = relationship(back_populates="metrics")


class DiscoveryRun(TimestampMixin, Base):
    __tablename__ = "discovery_runs"
    __table_args__ = (
        Index("ix_discovery_run_source", "source_id"),
        Index("ix_discovery_run_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="queued", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    query_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    results_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    candidates_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicates_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    candidates: Mapped[list[StartupDiscoveryCandidate]] = relationship(
        back_populates="discovery_run", cascade="all, delete-orphan"
    )


class StartupDiscoveryCandidate(TimestampMixin, Base):
    __tablename__ = "startup_discovery_candidates"
    __table_args__ = (
        Index("ix_discovery_candidate_source", "source_id"),
        Index("ix_discovery_candidate_status", "status"),
        Index("ix_discovery_candidate_normalized_name", "normalized_name"),
        Index("ix_discovery_candidate_website", "website"),
        Index("ix_discovery_candidate_confidence", "confidence"),
        Index("ix_discovery_candidate_run", "discovery_run_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    discovery_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("discovery_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    discovered_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    website: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    country: Mapped[str] = mapped_column(String(100), nullable=False, default="Brazil")
    sector: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    raw_text_excerpt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ai_native_signals_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    evidence_refs_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False, default="low", index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="new", index=True)
    promoted_startup_id: Mapped[str | None] = mapped_column(
        ForeignKey("startups.id", ondelete="SET NULL"), nullable=True, index=True
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    discovery_run: Mapped[DiscoveryRun | None] = relationship(back_populates="candidates")


class WorkflowRun(TimestampMixin, Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (
        Index("ix_workflow_run_startup", "startup_id"),
        Index("ix_workflow_run_analysis_run", "analysis_run_id"),
        Index("ix_workflow_run_status", "status"),
        Index("ix_workflow_run_current_node", "current_node"),
        Index("ix_workflow_run_graph_version", "graph_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    startup_id: Mapped[str | None] = mapped_column(
        ForeignKey("startups.id", ondelete="SET NULL"), nullable=True, index=True
    )
    discovery_candidate_id: Mapped[str | None] = mapped_column(
        ForeignKey("startup_discovery_candidates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    analysis_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="queued", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_node: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    graph_version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0")
    state_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text)
    degraded_reason: Mapped[str | None] = mapped_column(Text)

    node_runs: Mapped[list[WorkflowNodeRun]] = relationship(back_populates="workflow_run", cascade="all, delete-orphan")
    startup: Mapped[Startup | None] = relationship()
    discovery_candidate: Mapped[StartupDiscoveryCandidate | None] = relationship()
    analysis_run: Mapped[AnalysisRun | None] = relationship()


class OpportunityScoreRecord(TimestampMixin, Base):
    __tablename__ = "opportunity_score_records"
    __table_args__ = (
        Index("ix_opportunity_score_run_version", "analysis_run_id", "score_version"),
        Index("ix_opportunity_score_score", "opportunity_score"),
        Index("ix_opportunity_score_tier", "score_tier"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    score_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    opportunity_score: Mapped[float] = mapped_column(Float, nullable=False)
    score_tier: Mapped[str] = mapped_column(String(30), nullable=False)
    components_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    penalties_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    penalty_total: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    evidence_refs_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    recommended_action: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    reasoning: Mapped[str] = mapped_column(Text, nullable=False, default="")

    analysis_run: Mapped[AnalysisRun] = relationship()


class WorkflowNodeRun(TimestampMixin, Base):
    __tablename__ = "workflow_node_runs"
    __table_args__ = (
        Index("ix_workflow_node_run_workflow_node", "workflow_run_id", "node_name"),
        Index("ix_workflow_node_run_status", "status"),
        Index("ix_workflow_node_run_retry", "retry_count"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workflow_run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    node_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    input_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    output_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    workflow_run: Mapped[WorkflowRun] = relationship(back_populates="node_runs")
