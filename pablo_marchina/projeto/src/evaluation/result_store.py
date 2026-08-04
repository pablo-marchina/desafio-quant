from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.governance.schemas import BenchmarkType


class MetricResult(BaseModel):
    name: str
    value: float | str
    unit: str
    higher_is_better: bool | None = None


class BenchmarkResult(BaseModel):
    run_id: str
    candidate_id: str
    candidate_name: str
    dataset_id: str
    status: str
    benchmark_type: BenchmarkType = BenchmarkType.LOCAL_READINESS
    metrics: list[MetricResult] = Field(default_factory=list)
    latency_ms: float | None = None
    cost: float | None = None
    risk_score: float | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BenchmarkResultStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, result: BenchmarkResult) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(result.model_dump(mode="json"), sort_keys=True, ensure_ascii=True) + "\n")

    def load_all(self) -> list[BenchmarkResult]:
        if not self.path.exists():
            return []
        results: list[BenchmarkResult] = []
        with self.path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    results.append(BenchmarkResult.model_validate_json(line))
        return results
