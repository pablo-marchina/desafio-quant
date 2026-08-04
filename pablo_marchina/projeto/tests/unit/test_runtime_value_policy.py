from __future__ import annotations

from scripts.check_runtime_value_policy import build_runtime_value_policy_report


def test_runtime_value_policy_requires_runtime_evidence() -> None:
    report = build_runtime_value_policy_report(
        [
            {
                "component_id": "runtime.qdrant",
                "name": "Qdrant",
                "status": "PROMOTED_TO_RUNTIME",
                "runtime_role": "rag_vector_store",
                "benchmark_ref": "",
                "decision_ref": "decision.qdrant",
            }
        ],
        [],
    )

    assert report["status"] == "FAIL"
    assert report["components"][0]["missing_policy_fields"] == ["benchmark_ref"]


def test_runtime_value_policy_keeps_runtime_and_flags_free_external_comparison() -> None:
    report = build_runtime_value_policy_report(
        [
            {
                "component_id": "runtime.postgresql",
                "name": "PostgreSQL",
                "status": "PROMOTED_TO_RUNTIME",
                "runtime_role": "product_database",
                "benchmark_ref": "final_case_evidence/postgres_migration_report.json",
                "decision_ref": "decision.postgresql",
            }
        ],
        [
            {
                "name": "Supabase free tier",
                "status": "FUTURE_RESEARCH",
                "required_configuration": "free tier public API; no paid credentials required",
                "benchmark": "direct free external API benchmark when network is enabled",
            }
        ],
    )

    component = report["components"][0]
    assert report["status"] == "PASS"
    assert component["decision"] == "KEEP_RUNTIME_PENDING_BETTER_BENCHMARK"
    assert component["needs_free_external_comparison"] is True
    assert component["free_external_alternative_count"] == 1
