from __future__ import annotations

from scripts.build_runtime_usage_inventory import build_inventory


def test_runtime_usage_inventory_classifies_every_src_module() -> None:
    rows = build_inventory()

    assert rows
    assert all(row["type"] != "unclassified" for row in rows)
    assert {row["type"] for row in rows} <= {
        "runtime_active",
        "runtime_support",
        "governance_only",
        "candidate_only",
    }


def test_runtime_usage_inventory_marks_known_support_and_governance_modules() -> None:
    rows = {row["path"]: row for row in build_inventory()}

    assert rows["src/__init__.py"]["type"] == "runtime_support"
    assert rows["src/evaluation/rag_eval.py"]["type"] in {"runtime_active", "governance_only"}
    assert rows["src/sourcing/adaptive_source_planner.py"]["type"] in {"runtime_active", "candidate_only"}
