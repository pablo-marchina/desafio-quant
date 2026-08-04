from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from numbers import Real
from time import perf_counter
from typing import Any
from uuid import uuid4

from src.evaluation.dataset_registry import BenchmarkDataset
from src.evaluation.result_store import BenchmarkResult, BenchmarkResultStore, MetricResult
from src.governance.schemas import BenchmarkType

BenchmarkCallable = Callable[[BenchmarkDataset], dict[str, Any]]


@dataclass(frozen=True)
class BenchmarkCandidate:
    candidate_id: str
    name: str
    task: BenchmarkCallable | None = None
    substitute_for: str | None = None


class CostLatencyTracker:
    def __enter__(self) -> CostLatencyTracker:
        self._started = perf_counter()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.latency_ms = (perf_counter() - self._started) * 1000

    latency_ms: float = 0.0


class RiskAssessmentHook:
    def assess(self, result_payload: dict[str, Any]) -> float | None:
        risk = result_payload.get("risk_score")
        if risk is None:
            return None
        return float(risk)


class DecisionLedgerWriter:
    def build_decision(self, result: BenchmarkResult) -> dict[str, Any]:
        return {
            "decision_id": f"benchmark.{result.run_id}",
            "candidate_id": result.candidate_id,
            "status": "BENCHMARKED" if result.status == "passed" else "REJECTED_BY_EVIDENCE",
            "evidence_reference": result.run_id,
        }


class CalibrationRegistryWriter:
    def build_calibration_rows(self, result: BenchmarkResult) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for metric in result.metrics:
            rows.append(
                {
                    "calibration_id": f"{result.run_id}.{metric.name}",
                    "metric_name": metric.name,
                    "value": metric.value,
                    "unit": metric.unit,
                    "experiment_run_id": result.run_id,
                    "production_allowed": False,
                }
            )
        return rows


class BenchmarkRunner:
    def __init__(
        self,
        result_store: BenchmarkResultStore,
        risk_hook: RiskAssessmentHook | None = None,
    ) -> None:
        self.result_store = result_store
        self.risk_hook = risk_hook or RiskAssessmentHook()

    def run(self, candidate: BenchmarkCandidate, dataset: BenchmarkDataset) -> BenchmarkResult:
        run_id = str(uuid4())
        if candidate.task is None:
            result = BenchmarkResult(
                run_id=run_id,
                candidate_id=candidate.candidate_id,
                candidate_name=candidate.name,
                dataset_id=dataset.dataset_id,
                status="blocked",
                benchmark_type=BenchmarkType.PROXY,
                error="No executable benchmark task configured for candidate.",
                metadata={"substitute_for": candidate.substitute_for},
            )
            self.result_store.append(result)
            return result

        try:
            with CostLatencyTracker() as tracker:
                payload = candidate.task(dataset)
            metrics = [MetricResult.model_validate(metric) for metric in payload.get("metrics", [])]
            result = BenchmarkResult(
                run_id=run_id,
                candidate_id=candidate.candidate_id,
                candidate_name=candidate.name,
                dataset_id=dataset.dataset_id,
                status=str(payload.get("status", "passed")),
                benchmark_type=BenchmarkType(payload.get("benchmark_type", BenchmarkType.LOCAL_READINESS.value)),
                metrics=metrics,
                latency_ms=tracker.latency_ms,
                cost=_optional_float(payload.get("cost")),
                risk_score=self.risk_hook.assess(payload),
                metadata={"substitute_for": candidate.substitute_for, **payload.get("metadata", {})},
            )
        except Exception as exc:
            result = BenchmarkResult(
                run_id=run_id,
                candidate_id=candidate.candidate_id,
                candidate_name=candidate.name,
                dataset_id=dataset.dataset_id,
                status="failed",
                benchmark_type=BenchmarkType.LOCAL_READINESS,
                error=str(exc),
                metadata={"substitute_for": candidate.substitute_for},
            )

        self.result_store.append(result)
        return result


class AblationRunner:
    def run_ablation(
        self,
        baseline: BenchmarkResult,
        candidate: BenchmarkResult,
        metric_name: str,
    ) -> dict[str, float | str]:
        baseline_value = _metric_value(baseline, metric_name)
        candidate_value = _metric_value(candidate, metric_name)
        if baseline_value is None or candidate_value is None:
            return {"metric_name": metric_name, "status": "missing_metric"}
        return {
            "metric_name": metric_name,
            "status": "measured",
            "baseline": baseline_value,
            "candidate": candidate_value,
            "delta": candidate_value - baseline_value,
        }


class SensitivityAnalysisRunner:
    def summarize(self, results: list[BenchmarkResult], metric_name: str) -> dict[str, float | str]:
        values = [value for result in results if (value := _metric_value(result, metric_name)) is not None]
        if not values:
            return {"metric_name": metric_name, "status": "missing_metric"}
        return {
            "metric_name": metric_name,
            "status": "measured",
            "min": min(values),
            "max": max(values),
            "spread": max(values) - min(values),
        }


class RegressionBudgetEvaluator:
    def evaluate(
        self,
        baseline: BenchmarkResult,
        candidate: BenchmarkResult,
        metric_name: str,
    ) -> dict[str, str | float]:
        delta = AblationRunner().run_ablation(baseline, candidate, metric_name)
        if delta.get("status") != "measured":
            return {"metric_name": metric_name, "status": "missing_metric"}
        return {
            "metric_name": metric_name,
            "status": "TBD_BY_BASELINE",
            "delta": float(delta["delta"]),
        }


def _metric_value(result: BenchmarkResult, metric_name: str) -> float | None:
    for metric in result.metrics:
        if metric.name == metric_name and isinstance(metric.value, int | float):
            return float(metric.value)
    return None


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, Real):
        return float(value)
    if isinstance(value, str):
        return float(value)
    raise TypeError(f"Expected numeric cost value, got {type(value).__name__}")
