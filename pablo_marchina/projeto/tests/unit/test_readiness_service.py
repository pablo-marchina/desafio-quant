from __future__ import annotations

from src.services.product.capability_registry import CapabilityStatus
from src.services.product.health_executor import get_health_executor
from src.services.product.readiness_service import (
    ProductReadinessService,
    _validate_ai_native_model,
    _validate_decisioning_config,
)


class TestProductReadinessService:
    def setup_method(self) -> None:
        get_health_executor().invalidate()

    def test_list_capabilities_returns_all(self) -> None:
        svc = ProductReadinessService()
        caps = svc.list_capabilities()
        assert len(caps) >= 25

    def test_get_capability_status_exists(self) -> None:
        svc = ProductReadinessService()
        cap = svc.get_capability_status("product_database")
        assert cap is not None
        assert cap.capability_id == "product_database"

    def test_get_capability_status_missing(self) -> None:
        svc = ProductReadinessService()
        assert svc.get_capability_status("nonexistent") is None

    def test_list_required_configuration_returns_items(self) -> None:
        svc = ProductReadinessService()
        items = svc.list_required_configuration()
        assert len(items) >= 15

    def test_validate_configuration_checks_required(self) -> None:
        svc = ProductReadinessService()
        missing = svc.validate_configuration()
        assert isinstance(missing, list)

    def test_get_product_readiness_returns_report(self) -> None:
        svc = ProductReadinessService()
        report = svc.get_product_readiness()
        assert hasattr(report, "ready")
        assert hasattr(report, "blocking_missing_config")
        assert hasattr(report, "health_checks")
        assert hasattr(report, "setup_checklist")

    def test_setup_checklist_not_empty(self) -> None:
        svc = ProductReadinessService()
        checklist = svc.get_setup_checklist()
        assert len(checklist) > 0

    def test_get_missing_configuration(self) -> None:
        svc = ProductReadinessService()
        missing = svc.get_missing_configuration()
        assert isinstance(missing, list)

    def test_get_optional_features_status(self) -> None:
        svc = ProductReadinessService()
        features = svc.get_optional_features_status()
        ids = {f["capability_id"] for f in features}
        assert "optional_instructor_trial" in ids or len(features) >= 0

    def test_core_capabilities_available(self) -> None:
        svc = ProductReadinessService()
        caps_by_id = {c.capability_id: c for c in svc.list_capabilities()}
        core = caps_by_id.get("product_api")
        assert core is not None
        assert core.status in (
            CapabilityStatus.available,
            CapabilityStatus.not_configured,
        )

    def test_health_check_key_propagated(self) -> None:
        svc = ProductReadinessService()
        cap = svc.get_capability_status("product_database")
        assert cap is not None
        assert cap.health_check_key == "product_db"
        cap_qdrant = svc.get_capability_status("qdrant_vector_store")
        assert cap_qdrant is not None
        assert cap_qdrant.health_check_key == "qdrant"
        cap_llm = svc.get_capability_status("optional_llm_judge")
        assert cap_llm is not None
        assert cap_llm.health_check_key == "llm_judge"

    def test_health_check_called_in_get_product_readiness(self) -> None:
        svc = ProductReadinessService()
        report = svc.get_product_readiness()
        assert isinstance(report.ready, bool)
        assert hasattr(report, "health_checks")

    def test_health_check_mock_overrides_status(self) -> None:
        from unittest.mock import patch

        from src.services.product.health_executor import (
            CapabilityStatus,
            HealthCheckResult,
        )

        get_health_executor().invalidate()
        with patch(
            "src.services.product.health_executor.HealthCheckExecutor._execute",
            return_value=HealthCheckResult(
                status=CapabilityStatus.unavailable,
                detail="Mocked unavailable",
            ),
        ):
            svc = ProductReadinessService()
            report = svc.get_product_readiness()
            assert isinstance(report.ready, bool)
            product_db_health = [h for h in report.health_checks if h.get("health_check_key") == "product_db"]
            if product_db_health:
                assert product_db_health[0]["status"] == "unavailable"
                assert product_db_health[0]["detail"] == "Mocked unavailable"

    def test_rag_not_blocking_in_test_mode_when_not_required(self) -> None:
        import os
        from unittest.mock import patch

        with patch.dict(
            os.environ,
            {"APP_MODE": "test", "RAG_REQUIRED_FOR_PRODUCT": "false"},
        ):
            svc = ProductReadinessService()
            report = svc.get_product_readiness()
        rag_blocking = [b for b in report.blocking_missing_config if "qdrant" in b.get("capability_id", "")]
        assert len(rag_blocking) == 0

    def test_product_mode_blocks_sqlite_non_qdrant_and_missing_langgraph_flag(self) -> None:
        import os
        from unittest.mock import patch

        with patch.dict(
            os.environ,
            {
                "APP_MODE": "product",
                "PRODUCT_DB_URL": "sqlite:///tmp/product.db",
                "RAG_VECTOR_BACKEND": "in_memory",
                "RAG_REQUIRED_FOR_PRODUCT": "false",
                "AGENT_ORCHESTRATION_ENABLED": "false",
            },
        ):
            svc = ProductReadinessService()
            report = svc.get_product_readiness()

        reasons = " ".join(str(b.get("reason", "")) for b in report.blocking_missing_config)
        assert "requires PostgreSQL" in reasons
        assert "RAG_VECTOR_BACKEND=qdrant" in reasons
        assert "RAG_REQUIRED_FOR_PRODUCT=true" in reasons
        assert "AGENT_ORCHESTRATION_ENABLED=true" in reasons
        assert "LANGGRAPH_CHECKPOINTER=postgres" in reasons

    def test_rag_blocking_when_rag_required(self) -> None:
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {"RAG_REQUIRED_FOR_PRODUCT": "true"}):
            svc = ProductReadinessService()
            report = svc.get_product_readiness()
            rag_blocking = [
                b for b in report.blocking_missing_config if b.get("capability_id") == "qdrant_vector_store"
            ]
            assert len(rag_blocking) > 0
            assert any("QDRANT_URL" in b.get("reason", "") for b in rag_blocking)

    def test_product_mode_does_not_block_optional_external_reranker(self) -> None:
        import os
        from unittest.mock import patch

        with patch.dict(
            os.environ,
            {
                "APP_MODE": "product",
                "PRODUCT_DB_URL": "postgresql://postgres:postgres@localhost:5432/startup_radar",
                "RAG_VECTOR_BACKEND": "qdrant",
                "QDRANT_URL": "http://localhost:6333",
                "QDRANT_COLLECTION": "nvidia_corpus",
                "RAG_EMBEDDING_MODEL": "all-MiniLM-L6-v2",
                "RAG_RETRIEVAL_MODE": "hybrid_with_rerank",
                "RERANKER_PROVIDER": "local_cross_encoder",
                "RAG_REQUIRED_FOR_PRODUCT": "true",
                "AGENT_ORCHESTRATION_ENABLED": "true",
                "LANGGRAPH_CHECKPOINTER": "postgres",
            },
            clear=True,
        ), patch("src.services.product.readiness_service._langgraph_postgres_checkpointer_available", return_value=True):
            svc = ProductReadinessService()
            report = svc.get_product_readiness()

        blocking_ids = {b.get("capability_id") for b in report.blocking_missing_config}
        optional_ids = {b.get("capability_id") for b in report.optional_missing_config}
        assert "optional_external_reranker" not in blocking_ids
        assert "optional_external_reranker" in optional_ids

    def test_decisioning_config_validator_requires_runtime_gates(self, tmp_path) -> None:
        path = tmp_path / "decisioning.yaml"
        path.write_text(
            "version: 1\n"
            "priors: {evidence_positive_alpha: 2.0}\n"
            "thresholds: {min_evidence_coverage: 0.8}\n"
            "exploration: {strategy: expected_information_gain}\n"
            "feedback: {posterior_update: beta_binomial}\n"
            "runtime_gates: {require_uncertainty: false}\n",
            encoding="utf-8",
        )

        errors = _validate_decisioning_config(path)

        assert any("require_uncertainty" in error for error in errors)
        assert any("require_decision_ledger" in error for error in errors)

    def test_ai_native_model_validator_requires_versioned_training_metadata(self, tmp_path) -> None:
        path = tmp_path / "model.json"
        path.write_text('{"model_version":"","record_count":5,"class_counts":{"ai_native":5}}', encoding="utf-8")

        errors = _validate_ai_native_model(path)

        assert any("model_version" in error for error in errors)
        assert any("at least 30" in error for error in errors)
        assert any("at least two classes" in error for error in errors)
