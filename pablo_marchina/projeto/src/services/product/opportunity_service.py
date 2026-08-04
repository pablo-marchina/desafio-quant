"""Opportunity ranking from persisted analysis runs."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from src.database.models import (
    AnalysisRun,
    ProductQualityRun,
)
from src.quality.constants import (
    METRIC_EXPORT_READINESS_SCORE,
    METRIC_REVIEW_READINESS_SCORE,
)
from src.repositories.claim import ClaimRepository


class OpportunityService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_opportunities(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        status: str | None = None,
        recommended_motion: str | None = None,
        min_score: float | None = None,
        sector: str | None = None,
        has_degraded: bool | None = None,
        review_decision: str | None = None,
        order_by: str = "inception_fit_score",
    ) -> tuple[list[dict[str, Any]], int]:
        latest_run_ids = self._latest_completed_runs()
        if not latest_run_ids:
            return [], 0

        statement = (
            select(AnalysisRun)
            .where(AnalysisRun.id.in_(latest_run_ids))
            .options(
                selectinload(AnalysisRun.startup),
                selectinload(AnalysisRun.scores),
                selectinload(AnalysisRun.gaps),
                selectinload(AnalysisRun.mappings),
                selectinload(AnalysisRun.readiness_checks),
                selectinload(AnalysisRun.reviews),
            )
        )

        runs = list(set(self.session.scalars(statement).unique()))
        items: list[dict[str, Any]] = []
        for run in runs:
            startup = run.startup
            if startup is None:
                continue
            if status and startup.status != status:
                continue
            if sector and startup.sector != sector:
                continue

            scores = {s.score_type: s for s in run.scores}
            gaps = [g for g in run.gaps if g.detected]
            mappings = run.mappings
            degraded_count = sum(1 for rc in run.readiness_checks if rc.status in ("degraded", "error"))
            last_review = self._latest_review(run.reviews)

            if has_degraded is not None:
                if has_degraded and degraded_count == 0:
                    continue
                if not has_degraded and degraded_count > 0:
                    continue
            if review_decision and (last_review is None or last_review.decision != review_decision):
                continue

            recommended_motion_value = None
            composite_score_value = None
            confidence_value = None
            if run.output_snapshot_json:
                recommended_motion_value = run.output_snapshot_json.get("recommended_motion")
                composite_score_value = run.output_snapshot_json.get("composite_score", {}).get("composite_score")
                confidence_value = run.output_snapshot_json.get("composite_score", {}).get("confidence")

            if recommended_motion and recommended_motion_value != recommended_motion:
                continue

            inception_score = None
            if "inception_fit" in scores:
                inception_score = scores["inception_fit"].value
            if min_score is not None and (inception_score is None or inception_score < min_score):
                continue

            ai_native_score = None
            if "defensibility" in scores:
                ai_native_score = scores["defensibility"].value

            production_readiness_score = None
            if "production_readiness" in scores:
                production_readiness_score = scores["production_readiness"].value

            top_gaps = sorted(
                set(g.gap_type for g in gaps if g.detected),
                key=lambda gt: sum(1 for g in gaps if g.gap_type == gt and g.confidence == "high"),
                reverse=True,
            )
            top_nvidia_mappings = sorted(
                set(m.technology_name for m in mappings),
            )[:5]

            unsupported_claim_count: int | None = None
            evidence_coverage: float | None = None
            try:
                cov = ClaimRepository(self.session).get_evidence_coverage_summary(run.id)
                if cov["total_claims"] > 0:
                    unsupported_claim_count = cov["unsupported_claims"]
                    evidence_coverage = cov["evidence_coverage"]
            except Exception:
                pass

            quality_export_readiness: float | None = None
            quality_review_readiness: float | None = None
            try:
                quality_run = self._latest_quality_run(run.id)
                if quality_run is not None and quality_run.summary_json:
                    quality_export_readiness = quality_run.summary_json.get(METRIC_EXPORT_READINESS_SCORE)
                    quality_review_readiness = quality_run.summary_json.get(METRIC_REVIEW_READINESS_SCORE)
            except Exception:
                pass

            items.append(
                {
                    "startup_id": startup.id,
                    "startup_name": startup.name,
                    "latest_analysis_run_id": run.id,
                    "recommended_motion": recommended_motion_value,
                    "inception_fit_score": inception_score,
                    "ai_native_score": ai_native_score,
                    "production_readiness_score": production_readiness_score,
                    "composite_score": composite_score_value,
                    "confidence": confidence_value,
                    "status": startup.status,
                    "top_gaps": top_gaps,
                    "top_nvidia_mappings": top_nvidia_mappings,
                    "degraded_count": degraded_count,
                    "last_analyzed_at": run.completed_at,
                    "review_status": last_review.decision if last_review is not None else None,
                    "unsupported_claim_count": unsupported_claim_count,
                    "evidence_coverage": evidence_coverage,
                    "export_readiness_score": quality_export_readiness,
                    "review_readiness_score": quality_review_readiness,
                }
            )

        total = len(items)

        def _sort_confidence(item: dict[str, Any]) -> Any:
            confidence = item.get("confidence")
            if confidence:
                return {"high": 3, "medium": 2, "low": 1}.get(confidence, 0)
            return 0

        def _sort_last_analyzed(item: dict[str, Any]) -> Any:
            return item.get("last_analyzed_at") or ""

        def _sort_degraded(item: dict[str, Any]) -> Any:
            return item.get("degraded_count", 0)

        def _sort_inception_fit(item: dict[str, Any]) -> Any:
            return item.get("inception_fit_score") or -1

        if order_by == "confidence":
            sort_key = _sort_confidence
        elif order_by == "last_analyzed_at":
            sort_key = _sort_last_analyzed
        elif order_by == "degraded_count":
            sort_key = _sort_degraded
        else:
            sort_key = _sort_inception_fit

        items.sort(key=sort_key, reverse=True)
        page = items[offset : offset + limit]
        return page, total

    def _latest_completed_runs(self) -> list[str]:
        subq = (
            select(
                AnalysisRun.startup_id,
                func.max(AnalysisRun.created_at).label("max_created"),
            )
            .where(AnalysisRun.status.in_(["completed", "degraded"]))
            .group_by(AnalysisRun.startup_id)
        ).subquery()

        statement = (
            select(AnalysisRun.id)
            .join(
                subq,
                (AnalysisRun.startup_id == subq.c.startup_id) & (AnalysisRun.created_at == subq.c.max_created),
            )
            .where(AnalysisRun.status.in_(["completed", "degraded"]))
        )
        return [row[0] for row in self.session.execute(statement)]

    @staticmethod
    def _latest_review(reviews: list) -> Any | None:
        if not reviews:
            return None
        return max(reviews, key=lambda r: r.created_at)

    def _latest_quality_run(self, analysis_run_id: str) -> ProductQualityRun | None:
        stmt = (
            select(ProductQualityRun)
            .where(ProductQualityRun.analysis_run_id == analysis_run_id)
            .order_by(ProductQualityRun.created_at.desc())
            .limit(1)
        )
        return self.session.scalar(stmt)
