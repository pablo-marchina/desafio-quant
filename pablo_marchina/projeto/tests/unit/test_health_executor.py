from __future__ import annotations

import os
from unittest.mock import patch

from src.services.product.capability_registry import CapabilityStatus
from src.services.product.health_executor import (
    HealthCheckExecutor,
    HealthCheckResult,
)


class TestHealthCheckResult:
    def test_default_latency(self) -> None:
        r = HealthCheckResult(status=CapabilityStatus.available)
        assert r.latency_ms == 0.0
        assert r.detail == ""

    def test_unavailable_result(self) -> None:
        r = HealthCheckResult(
            status=CapabilityStatus.unavailable,
            detail="Connection refused",
        )
        assert r.status == CapabilityStatus.unavailable
        assert r.detail == "Connection refused"


class TestHealthCheckExecutor:
    def test_unknown_key_returns_available(self) -> None:
        executor = HealthCheckExecutor()
        result = executor.check("nonexistent_key")
        assert result.status == CapabilityStatus.available
        assert "No health check implemented" in result.detail

    def test_cache_returns_cached_result(self) -> None:
        executor = HealthCheckExecutor(cache_ttl=60.0)
        r1 = executor.check("nonexistent_key")
        r2 = executor.check("nonexistent_key")
        assert r1 is r2

    def test_invalidate_single_key(self) -> None:
        executor = HealthCheckExecutor(cache_ttl=60.0)
        executor.check("nonexistent_key")
        executor.invalidate("nonexistent_key")
        assert "nonexistent_key" not in executor._cache

    def test_invalidate_all(self) -> None:
        executor = HealthCheckExecutor(cache_ttl=60.0)
        executor.check("nonexistent_key")
        executor.invalidate()
        assert len(executor._cache) == 0

    @patch("src.services.product.health_executor.HealthCheckExecutor._check_product_db")
    def test_product_db_available(self, mock_check) -> None:
        mock_check.return_value = HealthCheckResult(
            status=CapabilityStatus.available,
            detail="Database responded to SELECT 1",
        )
        executor = HealthCheckExecutor()
        result = executor.check("product_db")
        assert result.status == CapabilityStatus.available
        assert "SELECT 1" in result.detail

    @patch("src.services.product.health_executor.HealthCheckExecutor._check_product_db")
    def test_product_db_unavailable(self, mock_check) -> None:
        mock_check.return_value = HealthCheckResult(
            status=CapabilityStatus.unavailable,
            detail="Database unreachable: connection refused",
        )
        executor = HealthCheckExecutor()
        result = executor.check("product_db")
        assert result.status == CapabilityStatus.unavailable

    @patch("src.services.product.health_executor.HealthCheckExecutor._check_qdrant")
    def test_qdrant_available(self, mock_check) -> None:
        mock_check.return_value = HealthCheckResult(
            status=CapabilityStatus.available,
            detail="Qdrant reachable, collection has 42 point(s)",
        )
        executor = HealthCheckExecutor()
        result = executor.check("qdrant")
        assert result.status == CapabilityStatus.available
        assert "42" in result.detail

    @patch("src.services.product.health_executor.HealthCheckExecutor._check_qdrant")
    def test_qdrant_unavailable(self, mock_check) -> None:
        mock_check.return_value = HealthCheckResult(
            status=CapabilityStatus.unavailable,
            detail="Qdrant unreachable",
        )
        executor = HealthCheckExecutor()
        result = executor.check("qdrant")
        assert result.status == CapabilityStatus.unavailable

    @patch("src.services.product.health_executor.HealthCheckExecutor._check_qdrant")
    def test_qdrant_empty_collection_is_degraded(self, mock_check) -> None:
        mock_check.return_value = HealthCheckResult(
            status=CapabilityStatus.degraded,
            detail="Qdrant collection exists but is empty",
        )
        executor = HealthCheckExecutor()
        result = executor.check("qdrant")
        assert result.status == CapabilityStatus.degraded

    @patch("src.services.product.health_executor.HealthCheckExecutor._check_rag_corpus")
    def test_rag_corpus_available(self, mock_check) -> None:
        mock_check.return_value = HealthCheckResult(
            status=CapabilityStatus.available,
            detail="Corpus found with 5 document(s)",
        )
        executor = HealthCheckExecutor()
        result = executor.check("rag")
        assert result.status == CapabilityStatus.available

    @patch("src.services.product.health_executor.HealthCheckExecutor._check_rag_corpus")
    def test_rag_corpus_missing_is_degraded(self, mock_check) -> None:
        mock_check.return_value = HealthCheckResult(
            status=CapabilityStatus.degraded,
            detail="Corpus directory exists but no markdown documents found",
        )
        executor = HealthCheckExecutor()
        result = executor.check("rag")
        assert result.status == CapabilityStatus.degraded

    def test_latency_is_recorded(self) -> None:
        executor = HealthCheckExecutor()
        result = executor.check("nonexistent_key")
        assert result.latency_ms >= 0.0

    @patch("src.services.product.health_executor.HealthCheckExecutor._check_llm_judge")
    def test_llm_judge_available(self, mock_check) -> None:
        mock_check.return_value = HealthCheckResult(
            status=CapabilityStatus.available,
            detail="LLM judge configured with provider=openai",
        )
        executor = HealthCheckExecutor()
        result = executor.check("llm_judge")
        assert result.status == CapabilityStatus.available
        assert "openai" in result.detail

    @patch("src.services.product.health_executor.HealthCheckExecutor._check_llm_judge")
    def test_llm_judge_unavailable(self, mock_check) -> None:
        mock_check.return_value = HealthCheckResult(
            status=CapabilityStatus.unavailable,
            detail="ANSWER_QUALITY_LLM_JUDGE_ENABLED is not set to true",
        )
        executor = HealthCheckExecutor()
        result = executor.check("llm_judge")
        assert result.status == CapabilityStatus.unavailable

    def test_llm_judge_uses_canonical_provider_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "ANSWER_QUALITY_LLM_JUDGE_ENABLED": "true",
                "ANSWER_QUALITY_LLM_JUDGE_PROVIDER": "null",
            },
            clear=True,
        ):
            executor = HealthCheckExecutor()
            result = executor.check("llm_judge")

        assert result.status == CapabilityStatus.degraded
        assert "ANSWER_QUALITY_LLM_JUDGE_PROVIDER=null" in result.detail
        assert "not a semantic quality judge" in result.detail

    def test_llm_judge_reports_missing_canonical_provider(self) -> None:
        with patch.dict(
            os.environ,
            {"ANSWER_QUALITY_LLM_JUDGE_ENABLED": "true"},
            clear=True,
        ):
            executor = HealthCheckExecutor()
            result = executor.check("llm_judge")

        assert result.status == CapabilityStatus.degraded
        assert "ANSWER_QUALITY_LLM_JUDGE_PROVIDER env var is not set" in result.detail

    def test_llm_judge_does_not_mark_unimplemented_provider_available(self) -> None:
        with patch.dict(
            os.environ,
            {
                "ANSWER_QUALITY_LLM_JUDGE_ENABLED": "true",
                "ANSWER_QUALITY_LLM_JUDGE_PROVIDER": "openai",
                "OPENAI_API_KEY": "test-key",
            },
            clear=True,
        ):
            executor = HealthCheckExecutor()
            result = executor.check("llm_judge")

        assert result.status == CapabilityStatus.degraded
        assert "has no active runtime provider implementation" in result.detail
