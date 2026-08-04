from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import ActivationRecommendationRecord


class ActivationRecommendationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_recommendation(
        self,
        *,
        analysis_run_id: str,
        playbook_id: str,
        playbook_name: str,
        matched_gap_types: list[str],
        matched_claim_ids: list[str],
        nvidia_technologies: list[str],
        technical_experiment: str,
        success_metrics: list[str],
        recommended_motion: str,
        priority: int,
        confidence: str,
        reasoning: str,
        evidence_refs: list[dict[str, Any]],
        risks: list[str],
        next_step: str,
    ) -> ActivationRecommendationRecord:
        record = ActivationRecommendationRecord(
            analysis_run_id=analysis_run_id,
            playbook_id=playbook_id,
            playbook_name=playbook_name,
            matched_gap_types_json=matched_gap_types,
            matched_claim_ids_json=matched_claim_ids,
            nvidia_technologies_json=nvidia_technologies,
            technical_experiment=technical_experiment,
            success_metrics_json=success_metrics,
            recommended_motion=recommended_motion,
            priority=priority,
            confidence=confidence,
            reasoning=reasoning,
            evidence_refs_json=evidence_refs,
            risks_json=risks,
            next_step=next_step,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def create_recommendations_bulk(
        self,
        records: list[dict[str, Any]],
    ) -> list[ActivationRecommendationRecord]:
        result: list[ActivationRecommendationRecord] = []
        for r in records:
            result.append(self.create_recommendation(**r))
        return result

    def replace_recommendations_for_analysis_run(
        self,
        analysis_run_id: str,
        records: list[dict[str, Any]],
    ) -> list[ActivationRecommendationRecord]:
        self.delete_for_analysis_run(analysis_run_id)
        for r in records:
            r["analysis_run_id"] = analysis_run_id
        return self.create_recommendations_bulk(records)

    def list_for_analysis_run(
        self,
        analysis_run_id: str,
    ) -> list[ActivationRecommendationRecord]:
        statement = (
            select(ActivationRecommendationRecord)
            .where(ActivationRecommendationRecord.analysis_run_id == analysis_run_id)
            .order_by(ActivationRecommendationRecord.priority.asc())
            .order_by(ActivationRecommendationRecord.created_at.desc())
        )
        return list(self.session.scalars(statement))

    def get_top_for_analysis_run(
        self,
        analysis_run_id: str,
    ) -> ActivationRecommendationRecord | None:
        statement = (
            select(ActivationRecommendationRecord)
            .where(ActivationRecommendationRecord.analysis_run_id == analysis_run_id)
            .order_by(ActivationRecommendationRecord.priority.asc())
            .order_by(ActivationRecommendationRecord.created_at.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def list_top_for_opportunities(
        self,
        analysis_run_ids: list[str],
    ) -> dict[str, ActivationRecommendationRecord]:
        if not analysis_run_ids:
            return {}
        statement = (
            select(ActivationRecommendationRecord)
            .where(
                ActivationRecommendationRecord.analysis_run_id.in_(analysis_run_ids),
            )
            .order_by(
                ActivationRecommendationRecord.analysis_run_id,
                ActivationRecommendationRecord.priority.asc(),
            )
        )
        rows = list(self.session.scalars(statement))
        result: dict[str, ActivationRecommendationRecord] = {}
        seen: set[str] = set()
        for row in rows:
            if row.analysis_run_id not in seen:
                seen.add(row.analysis_run_id)
                result[row.analysis_run_id] = row
        return result

    def delete_for_analysis_run(
        self,
        analysis_run_id: str,
    ) -> None:
        statement = select(ActivationRecommendationRecord).where(
            ActivationRecommendationRecord.analysis_run_id == analysis_run_id
        )
        records = list(self.session.scalars(statement))
        for r in records:
            self.session.delete(r)
        self.session.flush()
