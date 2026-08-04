from __future__ import annotations

from pathlib import Path

import pytest

from src.evaluation.benchmark_runner import (
    AblationRunner,
    BenchmarkCandidate,
    BenchmarkRunner,
    RegressionBudgetEvaluator,
    SensitivityAnalysisRunner,
)
from src.evaluation.dataset_registry import BenchmarkDataset
from src.evaluation.result_store import BenchmarkResultStore


def _dataset() -> BenchmarkDataset:
    return BenchmarkDataset(
        dataset_id="unit-dataset",
        name="Unit dataset",
        version="v1",
        path="tests/fixtures",
        task_type="unit",
        source_policy_ref="tests",
    )


def test_benchmark_runner_records_blocked_candidate(tmp_path: Path) -> None:
    store = BenchmarkResultStore(tmp_path / "results.jsonl")
    runner = BenchmarkRunner(store)
    result = runner.run(BenchmarkCandidate(candidate_id="paid-saas", name="Paid SaaS"), _dataset())
    assert result.status == "blocked"
    assert result.error is not None
    assert store.load_all()[0].candidate_id == "paid-saas"


def test_benchmark_runner_records_metrics(tmp_path: Path) -> None:
    def task(dataset: BenchmarkDataset) -> dict[str, object]:
        return {
            "status": "passed",
            "metrics": [{"name": "quality", "value": 0.8, "unit": "ratio", "higher_is_better": True}],
            "cost": 0.1,
            "risk_score": 0.2,
            "metadata": {"dataset": dataset.dataset_id},
        }

    store = BenchmarkResultStore(tmp_path / "results.jsonl")
    result = BenchmarkRunner(store).run(BenchmarkCandidate(candidate_id="local", name="Local", task=task), _dataset())
    assert result.status == "passed"
    assert result.metrics[0].name == "quality"
    assert result.cost == 0.1
    assert result.risk_score == 0.2
    assert result.latency_ms is not None


def test_ablation_sensitivity_and_regression_budget(tmp_path: Path) -> None:
    def make_task(value: float):
        def task(dataset: BenchmarkDataset) -> dict[str, object]:
            return {"metrics": [{"name": "quality", "value": value, "unit": "ratio"}]}

        return task

    store = BenchmarkResultStore(tmp_path / "results.jsonl")
    runner = BenchmarkRunner(store)
    baseline = runner.run(BenchmarkCandidate(candidate_id="base", name="Base", task=make_task(0.4)), _dataset())
    candidate = runner.run(
        BenchmarkCandidate(candidate_id="candidate", name="Candidate", task=make_task(0.7)),
        _dataset(),
    )

    ablation = AblationRunner().run_ablation(baseline, candidate, "quality")
    assert ablation["delta"] == pytest.approx(0.3)

    sensitivity = SensitivityAnalysisRunner().summarize([baseline, candidate], "quality")
    assert sensitivity["spread"] == pytest.approx(0.3)

    budget = RegressionBudgetEvaluator().evaluate(baseline, candidate, "quality")
    assert budget["status"] == "TBD_BY_BASELINE"
