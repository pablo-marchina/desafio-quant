"""ReviewDecision repository."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import ReviewDecision


class ReviewDecisionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        analysis_run_id: str,
        startup_id: str,
        decision: str,
        reviewer: str,
        notes: str = "",
        thread_id: str | None = None,
        review_payload_snapshot: dict[str, Any] | None = None,
        status_before_resume: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ReviewDecision:
        record = ReviewDecision(
            analysis_run_id=analysis_run_id,
            startup_id=startup_id,
            decision=decision,
            reviewer=reviewer,
            notes=notes,
            thread_id=thread_id,
            review_payload_snapshot=review_payload_snapshot,
            status_before_resume=status_before_resume,
            metadata_json=metadata or {},
        )
        self.session.add(record)
        self.session.flush()
        return record

    def update_status_after_resume(
        self,
        review_decision_id: str,
        status_after_resume: str,
    ) -> ReviewDecision | None:
        record = self.session.get(ReviewDecision, review_decision_id)
        if record is not None:
            record.status_after_resume = status_after_resume
            self.session.flush()
        return record

    def list_for_run(self, analysis_run_id: str) -> list[ReviewDecision]:
        statement = (
            select(ReviewDecision)
            .where(ReviewDecision.analysis_run_id == analysis_run_id)
            .order_by(ReviewDecision.created_at.desc())
        )
        return list(self.session.scalars(statement))

    def get_latest_for_run(self, analysis_run_id: str) -> ReviewDecision | None:
        statement = (
            select(ReviewDecision)
            .where(ReviewDecision.analysis_run_id == analysis_run_id)
            .order_by(ReviewDecision.created_at.desc())
            .limit(1)
        )
        return self.session.scalar(statement)
