"""Readiness Gate — FastAPI dependency that blocks requests when product is not ready."""

from __future__ import annotations

from fastapi import HTTPException, status

from src.services.product.readiness_service import ProductReadinessService


class ReadinessGate:
    def __call__(self) -> None:
        svc = ProductReadinessService()
        report = svc.get_product_readiness()
        if not report.ready:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": "Product is not ready",
                    "blocking_missing_config": report.blocking_missing_config,
                    "unavailable_capabilities": report.unavailable_capabilities,
                    "degraded_capabilities": report.degraded_capabilities,
                    "user_messages": report.user_messages,
                },
            )
