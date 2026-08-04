from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from src.services.product.readiness_gate import ReadinessGate
from src.services.product.readiness_service import ProductReadinessReport


class TestReadinessGate:
    def test_passes_when_ready(self) -> None:
        gate = ReadinessGate()
        report = ProductReadinessReport(ready=True)
        with patch(
            "src.services.product.readiness_service.ProductReadinessService.get_product_readiness",
            return_value=report,
        ):
            gate()

    def test_raises_503_when_not_ready(self) -> None:
        gate = ReadinessGate()
        report = ProductReadinessReport(
            ready=False,
            blocking_missing_config=[{"key": "PRODUCT_DB_URL", "reason": "not set"}],
            user_messages=["Required capability 'product_database' is not configured"],
        )
        with patch(
            "src.services.product.readiness_service.ProductReadinessService.get_product_readiness",
            return_value=report,
        ):
            with pytest.raises(HTTPException) as exc_info:
                gate()
            assert exc_info.value.status_code == 503
            detail = exc_info.value.detail
            assert detail["error"] == "Product is not ready"
            assert "blocking_missing_config" in detail
            assert "user_messages" in detail

    def test_detail_contains_all_fields(self) -> None:
        gate = ReadinessGate()
        report = ProductReadinessReport(
            ready=False,
            unavailable_capabilities=[{"capability_id": "qdrant_vector_store", "reason": "QDRANT_URL not set"}],
            degraded_capabilities=[{"capability_id": "rag_retrieval", "reason": "RAG backend degraded"}],
        )
        with patch(
            "src.services.product.readiness_service.ProductReadinessService.get_product_readiness",
            return_value=report,
        ):
            with pytest.raises(HTTPException) as exc_info:
                gate()
            detail = exc_info.value.detail
            assert "unavailable_capabilities" in detail
            assert detail["unavailable_capabilities"] == report.unavailable_capabilities
            assert "degraded_capabilities" in detail
            assert detail["degraded_capabilities"] == report.degraded_capabilities

    def test_503_uses_service_unavailable_status(self) -> None:
        gate = ReadinessGate()
        report = ProductReadinessReport(ready=False)
        with patch(
            "src.services.product.readiness_service.ProductReadinessService.get_product_readiness",
            return_value=report,
        ):
            with pytest.raises(HTTPException) as exc_info:
                gate()
            assert exc_info.value.status_code == 503
