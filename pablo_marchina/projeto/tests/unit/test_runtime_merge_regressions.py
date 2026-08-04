from __future__ import annotations

import json
from pathlib import Path

from src.agents.search_planner import build_search_plan


ROOT = Path(__file__).resolve().parents[2]


def _radar_dashboard_path() -> Path:
    matches = []
    for path in (ROOT / "frontend").rglob("*.tsx"):
        text = path.read_text(encoding="utf-8")
        if "function runtimeItemStatus" in text and "radar-runtime-card" in text:
            matches.append(path)
    assert len(matches) == 1
    return matches[0]


def test_search_planner_uses_defined_bounded_source_limit(monkeypatch) -> None:
    monkeypatch.setenv("RADAR_ANALYSIS_MAX_SOURCES", "2")
    plan = build_search_plan(
        "Maritaca AI",
        website_url="https://www.maritaca.ai/",
        known_source_urls=[
            "https://www.maritaca.ai/blog",
            "https://startups.com.br/maritaca-ai",
        ],
    )
    assert 1 <= len(plan) <= 2
    assert plan[0]["url"] == "https://www.maritaca.ai/"
    assert plan[0]["is_official_source"] is True


def test_collect_sources_defines_and_uses_combined_failures() -> None:
    text = (ROOT / "src/orchestration/node_impl.py").read_text(encoding="utf-8")
    assert "failures = critical_failures + degraded_failures" in text
    assert "status=NodeStatus.FAILED if is_failed else NodeStatus.DEGRADED" in text
    assert "known_source_urls=known_source_urls" in text


def test_quality_route_imports_timestamp_dependencies() -> None:
    text = (ROOT / "src/api/product_routes.py").read_text(encoding="utf-8")
    assert "from datetime import UTC, datetime" in text


def test_worker_has_process_healthcheck_and_logs_persisted_status() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    worker = (ROOT / "src/orchestration/worker.py").read_text(encoding="utf-8")
    assert "b'src.orchestration.worker'" in compose
    assert "workflow_finished_failed" in worker


def test_only_stable_public_directory_is_enabled_for_repaired_sources() -> None:
    sources = {
        item["source_id"]: item
        for item in json.loads((ROOT / "src/config/discovery_sources.json").read_text(encoding="utf-8"))
    }
    assert sources["open_startups_ecosystem"]["enabled_by_default"] is True
    assert sources["open_startups_ecosystem"]["base_url"].endswith("rankings-startups.html")
    for source_id in (
        "cubo_ecosystem",
        "distrito_startup_programs",
        "inovativa_startups",
        "bossa_invest_portfolio",
    ):
        assert sources[source_id]["enabled_by_default"] is False


def test_pipeline_results_expose_actionable_failure_details() -> None:
    backend = (ROOT / "src/services/product/radar_dashboard_service.py").read_text(encoding="utf-8")
    frontend = _radar_dashboard_path().read_text(encoding="utf-8")
    assert '"error": error or None' in backend
    assert '"current_node": workflow.current_node' in backend
    assert "function runtimeItemDetail" in frontend


def test_synchronous_workflow_is_reserved_before_worker_can_claim_it() -> None:
    source = (ROOT / "src/orchestration/service.py").read_text(encoding="utf-8")
    assert "initial_status: str = WorkflowStatus.QUEUED" in source
    assert "initial_status=WorkflowStatus.RUNNING" in source
    status_position = source.index("workflow_run.status = initial_status")
    commit_position = source.index("self.session.commit()", status_position)
    assert status_position < commit_position
