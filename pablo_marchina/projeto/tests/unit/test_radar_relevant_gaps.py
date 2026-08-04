from types import SimpleNamespace

from src.services.product.radar_dashboard_service import RadarDashboardService
from src.services.product.workload_classifier import classify_workloads


def test_big_data_and_data_science_map_to_tabular_ml() -> None:
    matches = classify_workloads(
        "Enterprise big data company applying machine learning, analytics and data science."
    )
    assert matches
    assert matches[0].family == "tabular_ml"


def test_dashboard_filters_gaps_to_supported_workloads_and_confidence() -> None:
    startup = SimpleNamespace(
        description="Conversational AI platform using NLP, LLM workflows and AI agents.",
        product_summary="",
        evidence=[],
    )
    gaps = [
        SimpleNamespace(gap_type="agent_governance_gap", detected=True, confidence="high"),
        SimpleNamespace(gap_type="model_evaluation_gap", detected=True, confidence="medium"),
        SimpleNamespace(gap_type="observability_gap", detected=True, confidence="medium"),
        SimpleNamespace(gap_type="computer_vision_need", detected=True, confidence="high"),
        SimpleNamespace(gap_type="robotics_need", detected=True, confidence="high"),
        SimpleNamespace(gap_type="high_latency", detected=True, confidence="low"),
    ]
    run = SimpleNamespace(
        startup=startup,
        output_snapshot_json={"startup_profile": {}},
        gaps=gaps,
    )

    assert RadarDashboardService._relevant_top_gaps(run) == [
        "agent_governance_gap",
        "observability_gap",
        "model_evaluation_gap",
    ]
