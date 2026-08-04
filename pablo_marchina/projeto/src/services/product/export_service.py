"""Export generation from persisted Action Brief records."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from src.database.models import ActionBriefRecord, AnalysisRun, ExportRecord
from src.repositories.export import ExportRepository
from src.repositories.product import ProductRepository


def _content_hash(data: dict[str, Any] | str) -> str:
    if isinstance(data, str):
        raw = data.encode("utf-8")
    else:
        raw = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


ACTION_BRIEF_EXPORT_FIELDS = (
    "run_id",
    "startup_id",
    "generated_at",
    "brief_status",
    "executive_summary_quantitative",
    "recommendation_summary",
    "top_recommendations",
    "evidence_summary",
    "rag_summary",
    "gap_summary",
    "scoring_summary",
    "risk_summary",
    "blockers",
    "next_best_actions",
    "audit_trail",
    "quality_gate_snapshot",
    "calibration_snapshot",
)


def persisted_action_brief_payload(
    run: AnalysisRun,
    brief: ActionBriefRecord,
) -> dict[str, Any]:
    brief_json = brief.brief_json or {}
    payload = {field: brief_json[field] for field in ACTION_BRIEF_EXPORT_FIELDS if field in brief_json}
    payload.setdefault("run_id", run.id)
    payload.setdefault("startup_id", run.startup_id)
    output_snapshot = run.output_snapshot_json or {}
    brief_metrics = output_snapshot.get("brief_metrics")
    payload["brief_metrics"] = brief_metrics if isinstance(brief_metrics, dict) else {}
    payload["schema_version"] = brief.schema_version
    return payload


def persisted_action_brief_json_export_payload(
    run: AnalysisRun,
    brief: ActionBriefRecord,
) -> dict[str, Any]:
    return {
        "export_metadata": {
            "export_id": str(uuid4()),
            "run_id": run.id,
            "exported_at": datetime.now(UTC),
            "export_format": "json",
            "source": "persisted_analysis_run_action_brief",
            "schema_version": brief.schema_version,
        },
        "action_brief": persisted_action_brief_payload(run, brief),
    }


class ExportService:
    def __init__(
        self,
        repository: ExportRepository,
        product_repo: ProductRepository,
        product_data_dir: str | None = None,
    ) -> None:
        self.repository = repository
        self.product_repo = product_repo
        self.product_data_dir = cast(str, product_data_dir or os.getenv("PRODUCT_DATA_DIR", "data/product"))

    def create_export(
        self,
        analysis_run_id: str,
        export_type: str,
    ) -> ExportRecord:
        run = self.product_repo.get_analysis_run(analysis_run_id)
        if run is None:
            raise LookupError(f"Analysis run not found: {analysis_run_id}")

        brief = self.product_repo.get_latest_action_brief(analysis_run_id)
        if brief is None:
            raise LookupError(f"Action brief not found for run: {analysis_run_id}")

        try:
            content: dict[str, Any] | str
            if export_type == "json":
                content = self._generate_json(brief)
            elif export_type == "markdown":
                content = self._generate_markdown(brief)
            else:
                raise ValueError(f"Unsupported export type: {export_type}")

            content_hash = _content_hash(content)
            storage_path = self._write_export(analysis_run_id, export_type, content)

            export = self.repository.create(
                analysis_run_id=analysis_run_id,
                action_brief_id=brief.id,
                export_type=export_type,
                status="completed",
                storage_path=storage_path,
                content_hash=content_hash,
            )
            self.repository.session.commit()
            return export
        except Exception as exc:
            export = self.repository.create(
                analysis_run_id=analysis_run_id,
                action_brief_id=brief.id,
                export_type=export_type,
                status="failed",
                error_message=str(exc),
            )
            raise

    def get_export(self, export_id: str) -> ExportRecord | None:
        return self.repository.get(export_id)

    def get_action_brief_json_export(self, analysis_run_id: str) -> dict[str, Any]:
        run = self.product_repo.get_analysis_run(analysis_run_id)
        if run is None:
            raise LookupError(f"Analysis run not found: {analysis_run_id}")
        brief = self.product_repo.get_latest_action_brief(analysis_run_id)
        if brief is None:
            raise LookupError(f"Action brief not found for run: {analysis_run_id}")
        return persisted_action_brief_json_export_payload(run, brief)

    def _generate_json(self, brief: ActionBriefRecord) -> dict[str, Any]:
        return brief.brief_json

    def _generate_markdown(self, brief: ActionBriefRecord) -> str:
        return brief.brief_markdown

    def _write_export(self, analysis_run_id: str, export_type: str, content: Any) -> str:
        product_data_dir = Path(self.product_data_dir).resolve()
        base = product_data_dir / "exports" / analysis_run_id
        base.mkdir(parents=True, exist_ok=True)
        extension = "json" if export_type == "json" else "md"
        file_path = base / f"action_brief.{extension}"
        if export_type == "json":
            file_path.write_text(
                json.dumps(content, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        else:
            file_path.write_text(str(content), encoding="utf-8")
        return str(file_path.relative_to(product_data_dir))
