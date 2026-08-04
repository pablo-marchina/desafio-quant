from __future__ import annotations

from pathlib import Path

from scripts.build_best_case_runtime_report import build_report


def test_best_case_runtime_report_contains_required_sections(tmp_path: Path) -> None:
    inventory = tmp_path / "runtime_usage_inventory.csv"
    inventory.write_text(
        "path,module,type,imported_by,endpoint_or_agent_using_it,evidence_file,decision,owner,deadline\n"
        "src/orchestration/runner.py,src.orchestration.runner,runtime_or_support,src.services.product.service,,"
        "final_case_evidence/runtime_usage_inventory.csv,keep,product,before_GO\n",
        encoding="utf-8",
    )

    report = build_report(inventory_path=inventory)

    assert report["report_id"] == "best_case_runtime_report"
    assert "final_proof" in report
    assert report["runtime_pipeline"]["central_pipeline"] == "LangGraph"
    assert report["runtime_pipeline"]["workflow_node_count"] >= 20
    assert report["rag_techniques"]["enabled_count"] > 0
    assert report["decisioning"]["probabilistic_scoring_module"]
    assert report["decisioning"]["config_present"] is True
    assert report["decisioning"]["runtime_gates"]["require_uncertainty"] is True
    assert report["ai_classifier"]["training_script"] == "scripts/train_ai_native_classifier.py"
    assert report["runtime_usage_inventory"]["row_count"] == 1
    assert report["gates"]["single_runtime_pipeline"]["status"] == "PASS"
    assert isinstance(report["known_gaps"], list)
