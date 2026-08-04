from __future__ import annotations

import json
from pathlib import Path

from scripts import run_free_external_candidate_benchmarks as probes


def test_probe_report_marks_missing_tools_blocked(tmp_path: Path, monkeypatch) -> None:
    review_path = tmp_path / "review.json"
    review_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "name": "OpenSSF Scorecard",
                        "ranking_eligible": True,
                        "output_value_family": "release_supply_chain",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(probes.shutil, "which", lambda command: None)
    monkeypatch.setattr(probes.importlib.util, "find_spec", lambda module: None)

    report = probes.build_probe_report(review_path)

    assert report["summary"]["eligible_candidate_count"] == 1
    assert report["summary"]["blocked_by_environment_count"] == 1
    assert report["probes"][0]["decision"] == "BLOCKED_BY_ENVIRONMENT"
    assert report["probes"][0]["quality_delta"] is None
    assert report["probes"][0]["value_hypothesis"]
    assert report["probes"][0]["output_quality_metrics"]
    assert report["probes"][0]["activation_commands"]


def test_probe_report_marks_installed_command_ready(tmp_path: Path, monkeypatch) -> None:
    review_path = tmp_path / "review.json"
    review_path.write_text(
        json.dumps({"items": [{"name": "Renovate", "ranking_eligible": True}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        probes.shutil, "which", lambda command: "C:/tools/renovate.cmd" if command == "renovate.cmd" else None
    )
    monkeypatch.setattr(probes.importlib.util, "find_spec", lambda module: None)

    report = probes.build_probe_report(review_path)

    assert report["summary"]["ready_for_product_benchmark_count"] == 1
    assert report["probes"][0]["status"] == "READY_FOR_PRODUCT_BENCHMARK"
    assert report["probes"][0]["decision"] == "PRODUCT_BENCHMARK_REQUIRED"
    assert "actionable_dependency_updates" in report["probes"][0]["output_quality_metrics"]


def test_probe_report_marks_version_command_ready(tmp_path: Path, monkeypatch) -> None:
    review_path = tmp_path / "review.json"
    review_path.write_text(
        json.dumps({"items": [{"name": "Renovate", "ranking_eligible": True}]}),
        encoding="utf-8",
    )

    class Result:
        returncode = 0
        stdout = "43.235.1\n"
        stderr = ""

    monkeypatch.setattr(probes.shutil, "which", lambda command: None)
    monkeypatch.setattr(probes.importlib.util, "find_spec", lambda module: None)
    monkeypatch.setattr(probes.subprocess, "run", lambda *args, **kwargs: Result())

    report = probes.build_probe_report(review_path)

    assert report["summary"]["ready_for_product_benchmark_count"] == 1
    assert report["probes"][0]["version_checks"][0]["available"] is True
    assert report["probes"][0]["version_checks"][0]["stdout_tail"] == "43.235.1\n"


def test_probe_report_marks_installed_module_ready(tmp_path: Path, monkeypatch) -> None:
    review_path = tmp_path / "review.json"
    review_path.write_text(
        json.dumps({"items": [{"name": "Argilla", "ranking_eligible": True}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(probes.shutil, "which", lambda command: None)
    monkeypatch.setattr(probes.importlib.util, "find_spec", lambda module: object() if module == "argilla" else None)

    report = probes.build_probe_report(review_path)

    assert report["summary"]["ready_for_product_benchmark_count"] == 1
    assert report["probes"][0]["modules_found"] == ["argilla"]


def test_probe_treats_missing_parent_module_as_unavailable(monkeypatch) -> None:
    def raise_missing(module: str) -> object:
        raise ModuleNotFoundError(module)

    monkeypatch.setattr(probes.importlib.util, "find_spec", raise_missing)

    assert probes._module_available("arize.phoenix") is False


def test_probe_markdown_report_contains_summary(tmp_path: Path) -> None:
    path = tmp_path / "report.md"
    report = {
        "status": "PASS",
        "summary": {
            "eligible_candidate_count": 1,
            "ready_for_product_benchmark_count": 0,
            "blocked_by_environment_count": 1,
        },
        "probes": [
            {
                "name": "OpenSSF Scorecard",
                "status": "BLOCKED_BY_ENVIRONMENT",
                "decision": "BLOCKED_BY_ENVIRONMENT",
                "reason": "tool missing",
                "value_hypothesis": "Improve output.",
                "output_quality_metrics": ["metric"],
                "benchmark_command": "python script.py",
                "activation_commands": ["install tool"],
            }
        ],
    }

    probes.write_markdown_report(path, report)

    text = path.read_text(encoding="utf-8")
    assert "Free External Candidate Benchmark Report" in text
    assert "OpenSSF Scorecard" in text
