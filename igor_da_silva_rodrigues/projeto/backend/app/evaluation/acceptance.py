from __future__ import annotations

import csv
import random
from collections import defaultdict
from pathlib import Path
from typing import Any
from uuid import UUID

from app.persistence.batch_repository import BatchRepository, TERMINAL_ITEM_STATUSES


REVIEW_FIELDS = [
    "reviewer",
    "classification_agreement",
    "evidence_agreement",
    "recommendation_applicable",
    "briefing_utility_1_5",
    "review_notes",
]


class AcceptanceSampleGenerator:
    """Generate a deterministic, stratified review sample from completed batch items."""

    def __init__(self, repository: BatchRepository) -> None:
        self.repository = repository
        self.persistence = repository.persistence

    def generate(
        self,
        batch_id: UUID,
        output_path: Path,
        sample_size: int = 10,
        seed: int = 20260627,
        allow_incomplete: bool = False,
    ) -> Path:
        batch = self.repository.get_batch(batch_id)
        items = [
            item
            for item in self.repository.list_items(batch_id)
            if item["status"] in TERMINAL_ITEM_STATUSES and item.get("pipeline_run_id")
        ]
        if not allow_incomplete and batch["status"] not in {"completed", "partial", "failed"}:
            raise ValueError("O lote ainda nao esta em estado terminal")
        if len(items) < sample_size:
            raise ValueError(
                f"Amostra requer {sample_size} itens com pipeline_run_id; disponiveis: {len(items)}"
            )
        selected = stratified_sample(items, sample_size=sample_size, seed=seed)
        rows = [self._review_row(batch_id, item, seed) for item in selected]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        return output_path

    def _review_row(self, batch_id: UUID, item: dict[str, Any], seed: int) -> dict[str, Any]:
        run_id = item["pipeline_run_id"]
        run = _first(
            self.persistence.db.table("pipeline_runs")
            .select("warnings,source_errors,errors")
            .eq("id", run_id)
            .limit(1)
            .execute()
        ) or {}
        evidences = (
            self.persistence.db.table("evidences")
            .select("id")
            .eq("pipeline_run_id", run_id)
            .execute()
            .data
            or []
        )
        recommendation = _first(
            self.persistence.db.table("recommendation_refinements")
            .select("fit_score")
            .eq("pipeline_run_id", run_id)
            .limit(1)
            .execute()
        ) or {}
        summary = item.get("result_summary") or {}
        row = {
            "sample_seed": seed,
            "batch_id": str(batch_id),
            "batch_item_id": item["id"],
            "pipeline_run_id": run_id,
            "startup_name": item["startup_name"],
            "pipeline_status": item["status"],
            "classification": summary.get("classificacao") or "",
            "maturity_level": summary.get("nivel_maturidade") or "",
            "impact_index": summary.get("indice_impacto") or "",
            "fit_score": recommendation.get("fit_score") or "",
            "evidence_count": len(evidences),
            "warning_count": len(run.get("warnings") or []),
            "source_error_count": len(run.get("source_errors") or []),
            "critical_error_count": len(run.get("errors") or []),
        }
        row.update({field: "" for field in REVIEW_FIELDS})
        return row


def stratified_sample(
    items: list[dict[str, Any]],
    sample_size: int,
    seed: int,
) -> list[dict[str, Any]]:
    if sample_size < 1 or sample_size > len(items):
        raise ValueError("sample_size deve estar entre 1 e o total de itens")
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        classification = (item.get("result_summary") or {}).get("classificacao") or "unknown"
        groups[(classification, item.get("status") or "unknown")].append(item)
    randomizer = random.Random(seed)
    for group in groups.values():
        randomizer.shuffle(group)

    selected: list[dict[str, Any]] = []
    ordered_keys = sorted(groups)
    while len(selected) < sample_size:
        progressed = False
        for key in ordered_keys:
            if groups[key] and len(selected) < sample_size:
                selected.append(groups[key].pop())
                progressed = True
        if not progressed:
            break
    return selected


def _first(response: Any) -> dict[str, Any] | None:
    data = getattr(response, "data", None)
    return data[0] if isinstance(data, list) and data else None
