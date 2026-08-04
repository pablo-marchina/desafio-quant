from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import ProductQualityMetric, ProductQualityRun


class ProductQualityRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_quality_run(
        self,
        *,
        analysis_run_id: str,
        dossier_id: str | None = None,
        action_brief_id: str | None = None,
    ) -> ProductQualityRun:
        record = ProductQualityRun(
            analysis_run_id=analysis_run_id,
            dossier_id=dossier_id,
            action_brief_id=action_brief_id,
            status="running",
            started_at=datetime.now(UTC),
            evaluator_version="1.0",
        )
        self.session.add(record)
        self.session.flush()
        return record

    def complete_quality_run(
        self,
        run_id: str,
        *,
        metrics_json: dict[str, Any] | None = None,
        summary_json: dict[str, Any] | None = None,
    ) -> ProductQualityRun | None:
        record = self.session.get(ProductQualityRun, run_id)
        if record is None:
            return None
        record.status = "completed"
        record.completed_at = datetime.now(UTC)
        if metrics_json is not None:
            record.metrics_json = metrics_json
        if summary_json is not None:
            record.summary_json = summary_json
        self.session.flush()
        return record

    def fail_quality_run(
        self,
        run_id: str,
        *,
        degraded_reason: str = "",
    ) -> ProductQualityRun | None:
        record = self.session.get(ProductQualityRun, run_id)
        if record is None:
            return None
        record.status = "failed"
        record.completed_at = datetime.now(UTC)
        record.degraded_reason = degraded_reason
        self.session.flush()
        return record

    def degrade_quality_run(
        self,
        run_id: str,
        *,
        degraded_reason: str = "",
        metrics_json: dict[str, Any] | None = None,
        summary_json: dict[str, Any] | None = None,
    ) -> ProductQualityRun | None:
        record = self.session.get(ProductQualityRun, run_id)
        if record is None:
            return None
        record.status = "degraded"
        record.completed_at = datetime.now(UTC)
        record.degraded_reason = degraded_reason
        if metrics_json is not None:
            record.metrics_json = metrics_json
        if summary_json is not None:
            record.summary_json = summary_json
        self.session.flush()
        return record

    def add_metric(self, metric: ProductQualityMetric) -> ProductQualityMetric:
        self.session.add(metric)
        self.session.flush()
        return metric

    def add_metrics_bulk(
        self,
        metrics: list[ProductQualityMetric],
    ) -> list[ProductQualityMetric]:
        for m in metrics:
            self.session.add(m)
        self.session.flush()
        return metrics

    def get_quality_run(self, run_id: str) -> ProductQualityRun | None:
        return self.session.get(ProductQualityRun, run_id)

    def list_quality_runs_for_analysis_run(
        self,
        analysis_run_id: str,
    ) -> list[ProductQualityRun]:
        stmt = (
            select(ProductQualityRun)
            .where(ProductQualityRun.analysis_run_id == analysis_run_id)
            .order_by(ProductQualityRun.created_at.desc())
        )
        return list(self.session.scalars(stmt))

    def get_latest_quality_run_for_analysis_run(
        self,
        analysis_run_id: str,
    ) -> ProductQualityRun | None:
        stmt = (
            select(ProductQualityRun)
            .where(ProductQualityRun.analysis_run_id == analysis_run_id)
            .order_by(ProductQualityRun.created_at.desc())
            .limit(1)
        )
        return self.session.scalar(stmt)

    def get_metrics_for_quality_run(
        self,
        quality_run_id: str,
    ) -> list[ProductQualityMetric]:
        stmt = (
            select(ProductQualityMetric)
            .where(ProductQualityMetric.quality_run_id == quality_run_id)
            .order_by(ProductQualityMetric.created_at.asc())
        )
        return list(self.session.scalars(stmt))

    def delete_quality_runs_for_analysis_run(self, analysis_run_id: str) -> int:
        stmt = select(ProductQualityRun).where(ProductQualityRun.analysis_run_id == analysis_run_id)
        records = list(self.session.scalars(stmt))
        count = len(records)
        for r in records:
            self.session.delete(r)
        self.session.flush()
        return count
