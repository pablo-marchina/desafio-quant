from __future__ import annotations

from src.database.session import configure_product_database, product_session, reset_product_database_runtime
from src.discovery.candidate_quality import evaluate_candidate_quality
from src.services.product.radar_dashboard_service import PopulateOptions, RadarDashboardService


BAD_NAMES = [
    ("Youtube", "https://www.youtube.com/channel/UCwj0JWfpPyx4X8ZUOQ_XsJA"),
    ("Youtube Startup Instagram AI", "https://www.instagram.com/abstartups/"),
    ("Programas de aceleração ativos", "https://darwinstartups.com/cart"),
    ("StartupRun Mantenedores", "https://example.com"),
    ("Xiaomi", "https://startupbase.com.br/"),
]


def test_runtime_entity_gate_rejects_navigation_social_and_global_brand_candidates() -> None:
    for name, website in BAD_NAMES:
        result = evaluate_candidate_quality(
            name=name,
            website=website,
            description="AI startup directory page with startup and AI words",
            source_id="runtime_regression_test",
            signal_count=3,
            evidence_count=2,
        )
        assert not result.accepted, f"{name} should not pass the runtime company gate: {result}"


def test_radar_dashboard_population_is_bounded_and_returns_real_analyzed_companies(tmp_path) -> None:
    reset_product_database_runtime()
    db_url = f"sqlite:///{(tmp_path / 'radar.db').as_posix()}"
    configure_product_database(db_url)
    with product_session() as session:
        service = RadarDashboardService(session)
        response = service.populate(
            PopulateOptions(
                limit=100,
                source_limit=0,
                pipeline_limit=5,
                run_pipeline=True,
                force_rerun=True,
            )
        )
        dashboard = response["dashboard"]

        assert response["discovery_results"][0]["candidates_created"] >= 40
        assert 1 <= dashboard["total"] <= 5
        assert 1 <= dashboard["analyzed_total"] <= 5
        assert len(response["pipeline_results"]) <= 5
        assert isinstance(response.get("discovery_queue"), list)
        assert isinstance(response.get("rejected_entities"), list)

        bad_names = {name.casefold() for name, _ in BAD_NAMES}
        for item in dashboard["items"]:
            assert item["row_type"] == "analyzed_startup"
            assert item["company_name"].casefold() not in bad_names
            assert item["website"] and "example.com" not in item["website"]
            assert item["recommendation_status"] in {"ready", "missing_recommendations"}
            if item["activation_recommendations"]:
                assert item["top_nvidia_technologies"], item["company_name"]
            assert item["information"].get("evidence_sources"), item["company_name"]

