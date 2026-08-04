from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.governance.schemas import (
    BenchmarkCandidateEntry,
    BenchmarkType,
    CandidateStatus,
    DecisionLedgerEntry,
    RuntimeBOMEntry,
)


def test_candidate_status_values_match_final_roadmap() -> None:
    assert {status.value for status in CandidateStatus} == {
        "DOCUMENTED_CANDIDATE",
        "BENCHMARK_CONFIGURED",
        "BENCHMARKED",
        "PROMOTED_TO_RUNTIME",
        "REJECTED_BY_EVIDENCE",
        "REMOVED_UNUSED",
        "FUTURE_RESEARCH",
    }


def test_benchmark_type_values_match_finalization_policy() -> None:
    assert {item.value for item in BenchmarkType} == {
        "LOCAL_READINESS",
        "PROXY",
        "OUTPUT_VALUE",
        "PRODUCTION_QUALITY",
        "SECURITY",
        "COST_LATENCY",
        "COMPLIANCE",
        "REPRODUCIBILITY",
    }


def test_candidate_entry_defaults_to_documented_candidate() -> None:
    entry = BenchmarkCandidateEntry(candidate_id="qdrant", name="Qdrant", category="Runtime core")
    assert entry.status == CandidateStatus.DOCUMENTED_CANDIDATE
    assert entry.baseline == "TBD_BY_BASELINE"
    assert entry.benchmark_type == BenchmarkType.LOCAL_READINESS


def test_candidate_runtime_promotion_requires_evidence() -> None:
    with pytest.raises(ValidationError):
        BenchmarkCandidateEntry(
            candidate_id="qdrant",
            name="Qdrant",
            category="Runtime core",
            status=CandidateStatus.PROMOTED_TO_RUNTIME,
        )


def test_decision_ledger_runtime_promotion_requires_benchmark_ref() -> None:
    with pytest.raises(ValidationError):
        DecisionLedgerEntry(
            decision_id="decision-1",
            item_name="Qdrant",
            category="Runtime core",
            status=CandidateStatus.PROMOTED_TO_RUNTIME,
            decision="Promote",
            evidence_reference="final_case_evidence/decision_ledger.csv",
        )


def test_runtime_bom_requires_promoted_runtime_component() -> None:
    with pytest.raises(ValidationError):
        RuntimeBOMEntry(
            component_id="runtime.fake",
            name="Fake runtime",
            category="Runtime core",
            version_or_source="none",
            status=CandidateStatus.DOCUMENTED_CANDIDATE,
            runtime_role="product_runtime",
            configuration_ref=".env.example",
            benchmark_ref="final_case_evidence/benchmark_manifest.json",
            decision_ref="final_case_evidence/decision_ledger.csv",
        )
