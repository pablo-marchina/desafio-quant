from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.evaluation.golden_set import GoldenCase, GoldenSet
from app.evaluation.harness import ActualCase, evaluate_golden_set


def _case(index: int) -> GoldenCase:
    return GoldenCase(
        case_id=f"case-{index}",
        startup=f"Startup {index}",
        pipeline_run_id=uuid4(),
        expected_classification="AI-enabled",
        expected_maturity=3,
        accepted_evidence_urls=[f"https://startup{index}.com/ia"],
        expected_nvidia_technologies=["Triton", "NIM"],
        briefing_utility_1_5=5,
        reviewed_by="Revisor NVIDIA",
    )


def _approved_set() -> GoldenSet:
    return GoldenSet(
        version="1.0.0",
        status="approved",
        created_at=datetime.now(UTC),
        cases=[_case(index) for index in range(10)],
    )


def test_draft_golden_set_cannot_generate_official_metrics():
    golden_set = GoldenSet(
        version="1.0.0-draft", status="draft", created_at=datetime.now(UTC)
    )

    with pytest.raises(ValueError, match="draft"):
        evaluate_golden_set(golden_set, {})


def test_approved_golden_set_requires_ten_reviewed_cases():
    with pytest.raises(ValueError, match="pelo menos 10 casos"):
        GoldenSet(
            version="1.0.0",
            status="approved",
            created_at=datetime.now(UTC),
            cases=[_case(1)],
        )


def test_evaluation_calculates_quality_and_groundedness_metrics():
    golden_set = _approved_set()
    actual = {
        case.case_id: ActualCase(
            startup=case.startup,
            classification="AI-enabled",
            maturity=3,
            evidence_urls=[str(case.accepted_evidence_urls[0]) + "/"],
            recommendations=["Triton", "NIM", "CUDA"],
            citations=[
                {
                    "tecnologia": "Triton",
                    "url_doc": "https://docs.nvidia.com/triton",
                    "trecho_doc": "Documentacao oficial suficientemente detalhada para fundamentar o uso.",
                },
                {
                    "tecnologia": "NIM",
                    "url_doc": "https://docs.nvidia.com/nim",
                    "trecho_doc": "Outro trecho oficial suficientemente detalhado para a recomendacao.",
                },
            ],
        )
        for case in golden_set.cases
    }

    report = evaluate_golden_set(golden_set, actual)

    assert report["metrics"]["classification_accuracy"] == 1.0
    assert report["metrics"]["maturity_mae"] == 0.0
    assert report["metrics"]["evidence_recall"] == 1.0
    assert report["metrics"]["recommendation_top3_precision"] == pytest.approx(0.6667)
    assert report["metrics"]["groundedness"] == pytest.approx(0.6667)
    assert report["overall_passed"] is False


def test_evaluation_fails_when_an_actual_case_is_missing():
    golden_set = _approved_set()

    with pytest.raises(ValueError, match="Resultado ausente"):
        evaluate_golden_set(golden_set, {})
