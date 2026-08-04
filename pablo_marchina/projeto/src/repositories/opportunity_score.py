from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.database.models import OpportunityScoreRecord


class OpportunityScoreRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        analysis_run_id: str,
        score_version: int,
        opportunity_score: float,
        score_tier: str,
        components: dict[str, Any],
        penalties: list[dict[str, Any]],
        penalty_total: float,
        evidence_refs: list[dict[str, Any]],
        recommended_action: str,
        reasoning: str,
    ) -> OpportunityScoreRecord:
        record = OpportunityScoreRecord(
            analysis_run_id=analysis_run_id,
            score_version=score_version,
            opportunity_score=opportunity_score,
            score_tier=score_tier,
            components_json=components,
            penalties_json=penalties,
            penalty_total=penalty_total,
            evidence_refs_json=evidence_refs,
            recommended_action=recommended_action,
            reasoning=reasoning,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def get_latest_for_analysis_run(
        self,
        analysis_run_id: str,
    ) -> OpportunityScoreRecord | None:
        statement = (
            select(OpportunityScoreRecord)
            .where(OpportunityScoreRecord.analysis_run_id == analysis_run_id)
            .order_by(OpportunityScoreRecord.score_version.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def get_max_version(
        self,
        analysis_run_id: str,
    ) -> int:
        statement = select(func.coalesce(func.max(OpportunityScoreRecord.score_version), 0)).where(
            OpportunityScoreRecord.analysis_run_id == analysis_run_id
        )
        result = self.session.execute(statement).scalar()
        return result or 0

    def replace_latest_for_analysis_run(
        self,
        analysis_run_id: str,
        opportunity_score: float,
        score_tier: str,
        components: dict[str, Any],
        penalties: list[dict[str, Any]],
        penalty_total: float,
        evidence_refs: list[dict[str, Any]],
        recommended_action: str,
        reasoning: str,
    ) -> OpportunityScoreRecord:
        next_version = self.get_max_version(analysis_run_id) + 1
        return self.create(
            analysis_run_id=analysis_run_id,
            score_version=next_version,
            opportunity_score=opportunity_score,
            score_tier=score_tier,
            components=components,
            penalties=penalties,
            penalty_total=penalty_total,
            evidence_refs=evidence_refs,
            recommended_action=recommended_action,
            reasoning=reasoning,
        )

    def list_for_analysis_run(
        self,
        analysis_run_id: str,
    ) -> list[OpportunityScoreRecord]:
        statement = (
            select(OpportunityScoreRecord)
            .where(OpportunityScoreRecord.analysis_run_id == analysis_run_id)
            .order_by(OpportunityScoreRecord.score_version.desc())
        )
        return list(self.session.scalars(statement))

    def list_latest_for_runs(
        self,
        analysis_run_ids: list[str],
    ) -> dict[str, OpportunityScoreRecord]:
        if not analysis_run_ids:
            return {}
        subq = (
            select(
                OpportunityScoreRecord.analysis_run_id,
                func.max(OpportunityScoreRecord.score_version).label("max_version"),
            )
            .where(OpportunityScoreRecord.analysis_run_id.in_(analysis_run_ids))
            .group_by(OpportunityScoreRecord.analysis_run_id)
        ).subquery()

        statement = select(OpportunityScoreRecord).join(
            subq,
            (OpportunityScoreRecord.analysis_run_id == subq.c.analysis_run_id)
            & (OpportunityScoreRecord.score_version == subq.c.max_version),
        )
        rows = list(self.session.scalars(statement))
        return {r.analysis_run_id: r for r in rows}

    def delete_for_analysis_run(
        self,
        analysis_run_id: str,
    ) -> None:
        statement = select(OpportunityScoreRecord).where(OpportunityScoreRecord.analysis_run_id == analysis_run_id)
        records = list(self.session.scalars(statement))
        for r in records:
            self.session.delete(r)
        self.session.flush()
