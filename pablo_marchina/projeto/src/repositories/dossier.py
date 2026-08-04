from __future__ import annotations

from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.database.models import ActivationDossierRecord


class ActivationDossierRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_dossier(
        self,
        *,
        analysis_run_id: str,
        version: int,
        schema_version: str,
        dossier_json: dict[str, Any],
        dossier_markdown: str,
        evidence_coverage: float,
        unsupported_claim_count: int,
        top_activation_playbook_id: str | None,
        recommended_motion: str,
        review_status: str | None,
    ) -> ActivationDossierRecord:
        record = ActivationDossierRecord(
            analysis_run_id=analysis_run_id,
            version=version,
            schema_version=schema_version,
            dossier_json=dossier_json,
            dossier_markdown=dossier_markdown,
            is_latest=True,
            evidence_coverage=evidence_coverage,
            unsupported_claim_count=unsupported_claim_count,
            top_activation_playbook_id=top_activation_playbook_id,
            recommended_motion=recommended_motion,
            review_status=review_status,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def get_latest_for_analysis_run(self, analysis_run_id: str) -> ActivationDossierRecord | None:
        statement = (
            select(ActivationDossierRecord)
            .where(
                ActivationDossierRecord.analysis_run_id == analysis_run_id,
                ActivationDossierRecord.is_latest.is_(True),
            )
            .order_by(ActivationDossierRecord.version.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def list_for_analysis_run(self, analysis_run_id: str) -> list[ActivationDossierRecord]:
        statement = (
            select(ActivationDossierRecord)
            .where(ActivationDossierRecord.analysis_run_id == analysis_run_id)
            .order_by(ActivationDossierRecord.version.desc())
        )
        return list(self.session.scalars(statement))

    def mark_previous_not_latest(self, analysis_run_id: str) -> None:
        self.session.execute(
            update(ActivationDossierRecord)
            .where(
                ActivationDossierRecord.analysis_run_id == analysis_run_id,
                ActivationDossierRecord.is_latest.is_(True),
            )
            .values(is_latest=False)
        )
        self.session.flush()

    def get_by_id(self, dossier_id: str) -> ActivationDossierRecord | None:
        return self.session.get(ActivationDossierRecord, dossier_id)

    def next_version_for_analysis_run(self, analysis_run_id: str) -> int:
        current = self.get_latest_for_analysis_run(analysis_run_id)
        if current is None:
            return 1
        return current.version + 1

    def delete_for_analysis_run(self, analysis_run_id: str) -> None:
        statement = select(ActivationDossierRecord).where(ActivationDossierRecord.analysis_run_id == analysis_run_id)
        for record in self.session.scalars(statement):
            self.session.delete(record)
        self.session.flush()

    def count_for_analysis_run(self, analysis_run_id: str) -> int:
        statement = select(ActivationDossierRecord).where(ActivationDossierRecord.analysis_run_id == analysis_run_id)
        return len(list(self.session.scalars(statement)))
