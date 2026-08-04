"""Repositories for transactional product records."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Select, select, update
from sqlalchemy.orm import Session, selectinload

from src.database.models import (
    ActionBriefRecord,
    AnalysisRun,
    GapDiagnosisRecord,
    NvidiaMappingRecord,
    ProductReadinessCheck,
    ScoreRecord,
    Startup,
    StartupEvidence,
)


def normalize_startup_name(name: str) -> str:
    return " ".join(name.casefold().split())


class ProductRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_startup(
        self,
        *,
        name: str,
        website: str,
        country: str,
        sector: str,
        description: str,
        product_summary: str,
        status: str = "active",
        tags: list[str] | None = None,
    ) -> Startup:
        startup = Startup(
            name=name.strip(),
            normalized_name=normalize_startup_name(name),
            website=website,
            country=country,
            sector=sector,
            description=description,
            product_summary=product_summary,
            status=status,
            tags_json=tags or [],
        )
        self.session.add(startup)
        self.session.flush()
        return startup

    def list_startups(self, *, offset: int = 0, limit: int = 100) -> list[Startup]:
        statement = (
            select(Startup)
            .options(selectinload(Startup.evidence))
            .order_by(Startup.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.session.scalars(statement))

    def get_startup(self, startup_id: str) -> Startup | None:
        statement = select(Startup).where(Startup.id == startup_id).options(selectinload(Startup.evidence))
        return self.session.scalar(statement)

    def update_startup(self, startup_id: str, **changes: Any) -> Startup | None:
        startup = self.get_startup(startup_id)
        if startup is None:
            return None
        if "name" in changes:
            changes["normalized_name"] = normalize_startup_name(str(changes["name"]))
        for field, value in changes.items():
            if hasattr(startup, field):
                setattr(startup, field, value)
        self.session.flush()
        return startup

    def update_startup_fields(self, startup_id: str, fields: dict[str, Any]) -> Startup | None:
        startup = self.get_startup(startup_id)
        if startup is None:
            return None
        if "name" in fields:
            fields["normalized_name"] = normalize_startup_name(str(fields["name"]))
        for field, value in fields.items():
            if hasattr(startup, field):
                setattr(startup, field, value)
        self.session.flush()
        return startup

    def add_evidence(
        self,
        *,
        startup_id: str,
        claim: str,
        source_url: str,
        source_type: str,
        quote_or_evidence: str,
        confidence: str,
        collected_at: datetime,
        evidence_kind: str = "unverified",
        metadata: dict[str, Any] | None = None,
    ) -> StartupEvidence:
        evidence = StartupEvidence(
            startup_id=startup_id,
            claim=claim,
            source_url=source_url,
            source_type=source_type,
            quote_or_evidence=quote_or_evidence,
            confidence=confidence,
            evidence_kind=evidence_kind,
            collected_at=collected_at,
            metadata_json=metadata or {},
        )
        self.session.add(evidence)
        self.session.flush()
        return evidence

    def sync_validated_evidence(
        self,
        *,
        startup_id: str,
        validated_evidence: list[dict[str, Any]],
    ) -> None:
        startup = self.get_startup(startup_id)
        if startup is None:
            return
        by_key = {(item.claim, item.source_url): item for item in startup.evidence}
        for item in validated_evidence:
            key = (str(item["claim"]), str(item["source_url"]))
            existing = by_key.get(key)
            if existing is None:
                continue
            existing.confidence = str(item["confidence"])
            existing.evidence_kind = str(item["evidence_kind"])
        self.session.flush()

    def create_analysis_run(
        self,
        *,
        startup_id: str,
        input_snapshot: dict[str, Any],
        pipeline_version: str,
        corpus_version: str | None,
        config_snapshot: dict[str, Any],
    ) -> AnalysisRun:
        run = AnalysisRun(
            startup_id=startup_id,
            status="queued",
            input_snapshot_json=input_snapshot,
            pipeline_version=pipeline_version,
            corpus_version=corpus_version,
            config_snapshot_json=config_snapshot,
        )
        self.session.add(run)
        self.session.flush()
        return run

    def update_analysis_run_status(
        self,
        analysis_run_id: str,
        *,
        status: str,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        error_message: str | None = None,
        degraded_reason: str | None = None,
        output_snapshot: dict[str, Any] | None = None,
    ) -> AnalysisRun:
        run = self.session.get(AnalysisRun, analysis_run_id)
        if run is None:
            raise LookupError(f"AnalysisRun not found: {analysis_run_id}")
        run.status = status
        if started_at is not None:
            run.started_at = started_at
        if completed_at is not None:
            run.completed_at = completed_at
        run.error_message = error_message
        run.degraded_reason = degraded_reason
        if output_snapshot is not None:
            run.output_snapshot_json = output_snapshot
        self.session.flush()
        return run

    def save_score(
        self,
        *,
        analysis_run_id: str,
        score_type: str,
        value: float,
        confidence: str,
        components: dict[str, Any],
        missing_evidence: list[str],
    ) -> ScoreRecord:
        record = ScoreRecord(
            analysis_run_id=analysis_run_id,
            score_type=score_type,
            value=value,
            confidence=confidence,
            components_json=components,
            missing_evidence_json=missing_evidence,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def save_gap(
        self,
        *,
        analysis_run_id: str,
        gap_type: str,
        detected: bool,
        confidence: str,
        evidence_tag: str,
        reasoning: str,
        evidence_refs: list[dict[str, Any]],
        missing_evidence: list[str] | None = None,
    ) -> GapDiagnosisRecord:
        record = GapDiagnosisRecord(
            analysis_run_id=analysis_run_id,
            gap_type=gap_type,
            detected=detected,
            confidence=confidence,
            evidence_tag=evidence_tag,
            reasoning=reasoning,
            evidence_refs_json=evidence_refs,
            missing_evidence_json=missing_evidence or [],
        )
        self.session.add(record)
        self.session.flush()
        return record

    def save_mapping(
        self,
        *,
        analysis_run_id: str,
        gap_record_id: str | None,
        technology_name: str,
        addresses_gap: str,
        justification: str,
        recommendation_action: str | None,
        priority: str | None,
        details: dict[str, Any] | None = None,
    ) -> NvidiaMappingRecord:
        record = NvidiaMappingRecord(
            analysis_run_id=analysis_run_id,
            gap_record_id=gap_record_id,
            technology_name=technology_name,
            addresses_gap=addresses_gap,
            justification=justification,
            recommendation_action=recommendation_action,
            priority=priority,
            details_json=details or {},
        )
        self.session.add(record)
        self.session.flush()
        return record

    def save_action_brief(
        self,
        *,
        analysis_run_id: str,
        version: int,
        schema_version: str,
        brief_json: dict[str, Any],
        brief_markdown: str,
    ) -> ActionBriefRecord:
        self.session.execute(
            update(ActionBriefRecord)
            .where(ActionBriefRecord.analysis_run_id == analysis_run_id)
            .values(is_latest=False)
        )
        record = ActionBriefRecord(
            analysis_run_id=analysis_run_id,
            version=version,
            schema_version=schema_version,
            brief_json=brief_json,
            brief_markdown=brief_markdown,
            is_latest=True,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def save_readiness_check(
        self,
        *,
        analysis_run_id: str | None,
        code: str,
        severity: str,
        status: str,
        user_message: str,
        internal_detail: str,
        recommended_action: str,
        metadata: dict[str, Any] | None = None,
    ) -> ProductReadinessCheck:
        record = ProductReadinessCheck(
            analysis_run_id=analysis_run_id,
            code=code,
            severity=severity,
            status=status,
            user_message=user_message,
            internal_detail=internal_detail,
            recommended_action=recommended_action,
            metadata_json=metadata or {},
        )
        self.session.add(record)
        self.session.flush()
        return record

    def get_analysis_run(self, analysis_run_id: str) -> AnalysisRun | None:
        statement: Select[tuple[AnalysisRun]] = (
            select(AnalysisRun)
            .where(AnalysisRun.id == analysis_run_id)
            .options(
                selectinload(AnalysisRun.scores),
                selectinload(AnalysisRun.gaps),
                selectinload(AnalysisRun.mappings),
                selectinload(AnalysisRun.briefs),
                selectinload(AnalysisRun.readiness_checks),
            )
        )
        return self.session.scalar(statement)

    def get_latest_analysis_run(self, startup_id: str) -> AnalysisRun | None:
        statement = (
            select(AnalysisRun)
            .where(AnalysisRun.startup_id == startup_id)
            .order_by(AnalysisRun.created_at.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def get_latest_action_brief(self, analysis_run_id: str) -> ActionBriefRecord | None:
        statement = (
            select(ActionBriefRecord)
            .where(
                ActionBriefRecord.analysis_run_id == analysis_run_id,
                ActionBriefRecord.is_latest.is_(True),
            )
            .order_by(ActionBriefRecord.version.desc())
            .limit(1)
        )
        return self.session.scalar(statement)
