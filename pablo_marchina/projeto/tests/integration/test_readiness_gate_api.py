"""Integration tests for ReadinessGate — validates routes are blocked when product is not ready."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app
from src.services.product.readiness_service import ProductReadinessReport

client = TestClient(app)


class TestReadinessGateOnProductRoutes:
    def test_create_startup_blocked_when_not_ready(self) -> None:
        report = ProductReadinessReport(
            ready=False,
            blocking_missing_config=[{"key": "PRODUCT_DB_URL", "reason": "not set"}],
        )
        with patch(
            "src.services.product.readiness_service.ProductReadinessService.get_product_readiness",
            return_value=report,
        ):
            resp = client.post(
                "/startups",
                json={"name": "Test", "website": "https://example.com", "sector": "AI"},
            )
        assert resp.status_code == 503
        assert resp.json()["detail"]["error"] == "Product is not ready"

    def test_update_startup_blocked_when_not_ready(self) -> None:
        report = ProductReadinessReport(ready=False)
        with patch(
            "src.services.product.readiness_service.ProductReadinessService.get_product_readiness",
            return_value=report,
        ):
            resp = client.patch("/startups/nonexistent", json={"name": "Test"})
        assert resp.status_code == 503

    def test_create_analysis_run_blocked_when_not_ready(self) -> None:
        report = ProductReadinessReport(ready=False)
        with patch(
            "src.services.product.readiness_service.ProductReadinessService.get_product_readiness",
            return_value=report,
        ):
            resp = client.post(
                "/startups/nonexistent/analysis-runs",
                json={"use_rag": False},
            )
        assert resp.status_code == 503

    def test_create_dossier_blocked_when_not_ready(self) -> None:
        report = ProductReadinessReport(ready=False)
        with patch(
            "src.services.product.readiness_service.ProductReadinessService.get_product_readiness",
            return_value=report,
        ):
            resp = client.post("/analysis-runs/nonexistent/dossier")
        assert resp.status_code == 503

    def test_create_quality_run_blocked_when_not_ready(self) -> None:
        report = ProductReadinessReport(ready=False)
        with patch(
            "src.services.product.readiness_service.ProductReadinessService.get_product_readiness",
            return_value=report,
        ):
            resp = client.post("/analysis-runs/nonexistent/quality-runs")
        assert resp.status_code == 503

    def test_create_export_blocked_when_not_ready(self) -> None:
        report = ProductReadinessReport(ready=False)
        with patch(
            "src.services.product.readiness_service.ProductReadinessService.get_product_readiness",
            return_value=report,
        ):
            resp = client.post(
                "/analysis-runs/nonexistent/exports",
                json={"export_type": "json"},
            )
        assert resp.status_code == 503

    def test_compute_opportunity_score_blocked_when_not_ready(self) -> None:
        report = ProductReadinessReport(ready=False)
        with patch(
            "src.services.product.readiness_service.ProductReadinessService.get_product_readiness",
            return_value=report,
        ):
            resp = client.post("/analysis-runs/nonexistent/opportunity-score")
        assert resp.status_code == 503

    def test_generate_activation_recommendations_blocked_when_not_ready(self) -> None:
        report = ProductReadinessReport(ready=False)
        with patch(
            "src.services.product.readiness_service.ProductReadinessService.get_product_readiness",
            return_value=report,
        ):
            resp = client.post("/analysis-runs/nonexistent/activation-recommendations/generate")
        assert resp.status_code == 503

    def test_create_review_blocked_when_not_ready(self) -> None:
        report = ProductReadinessReport(ready=False)
        with patch(
            "src.services.product.readiness_service.ProductReadinessService.get_product_readiness",
            return_value=report,
        ):
            resp = client.post(
                "/analysis-runs/nonexistent/review",
                json={"decision": "approve", "reviewer": "test"},
            )
        assert resp.status_code == 503

    def test_read_routes_are_not_blocked(self) -> None:
        report = ProductReadinessReport(ready=False)
        with patch(
            "src.services.product.readiness_service.ProductReadinessService.get_product_readiness",
            return_value=report,
        ):
            resp = client.get("/product/capabilities")
        assert resp.status_code == 200


class TestReadinessGateOnWorkflowRoutes:
    def test_create_workflow_run_blocked_when_not_ready(self) -> None:
        report = ProductReadinessReport(ready=False)
        with patch(
            "src.services.product.readiness_service.ProductReadinessService.get_product_readiness",
            return_value=report,
        ):
            resp = client.post("/workflows/product-runs", json={})
        assert resp.status_code == 503
