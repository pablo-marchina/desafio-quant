from __future__ import annotations

from scripts.check_roadmap_closure_audit import build_report


def test_roadmap_closure_covers_all_marcos_and_formally_classifies_non_runtime_items() -> None:
    report = build_report()

    assert report["status"] == "PASS"
    assert report["marco_count"] == 23
    assert {item["marco"] for item in report["items"]} == set(range(23))

    marco_22 = next(item for item in report["items"] if item["marco"] == 22)
    assert marco_22["status"] == "BLOCKED_BY_ENVIRONMENT"
    assert "Real services remain environment-dependent." in marco_22["blocking_reason"]


def test_roadmap_closure_keeps_missing_refs_visible() -> None:
    report = build_report()

    assert all("evidence_refs" in item for item in report["items"])
    assert all("missing_required_refs" in item for item in report["items"])
    assert any(item["remaining_gaps"] for item in report["items"])
    assert not any(item["status"] == "PARTIAL" for item in report["items"])
