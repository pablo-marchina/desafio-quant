from __future__ import annotations

from pathlib import Path

import pytest

from scripts.check_product_configuration import _load_env_example
from scripts.product_doctor import build_product_doctor_report
from src.config.product_config_validator import validate_product_configuration


def _base_product_env() -> dict[str, str]:
    return {
        "APP_MODE": "product",
        "PRODUCT_DB_URL": "postgresql://postgres:postgres@localhost:5432/startup_radar",
        "RAG_VECTOR_BACKEND": "qdrant",
        "RAG_REQUIRED_FOR_PRODUCT": "true",
        "RAG_EMBEDDING_MODEL": "sentence-transformers/all-MiniLM-L6-v2",
        "RAG_RETRIEVAL_MODE": "hybrid_with_rerank",
        "RERANKER_PROVIDER": "local_cross_encoder",
        "RERANKER_MODEL": "BAAI/bge-reranker-v2-m3",
        "QDRANT_URL": "http://localhost:6333",
        "QDRANT_COLLECTION": "nvidia_corpus",
        "QDRANT_VECTOR_SIZE": "384",
        "AGENT_ORCHESTRATION_ENABLED": "true",
        "LANGGRAPH_CHECKPOINTER": "postgres",
        "ANSWER_QUALITY_LLM_JUDGE_ENABLED": "false",
        "SOURCE_COMPLIANCE_ENFORCED": "true",
        "SECURITY_SUITE_REQUIRED": "true",
    }


def test_product_configuration_accepts_hybrid_reranked_rag() -> None:
    report = validate_product_configuration(_base_product_env())

    assert report.status == "PASS"


def test_product_configuration_blocks_dense_only_rag_in_product_mode() -> None:
    env = _base_product_env()
    env["RAG_RETRIEVAL_MODE"] = "dense_only"

    report = validate_product_configuration(env)

    assert report.status == "FAIL"
    assert any(check.check_id == "rag.hybrid_retrieval_required" for check in report.failures)


def test_product_configuration_blocks_missing_reranker_in_product_mode() -> None:
    env = _base_product_env()
    env["RERANKER_PROVIDER"] = "none"

    report = validate_product_configuration(env)

    assert report.status == "FAIL"
    assert any(check.check_id == "rag.reranker_required" for check in report.failures)


def test_env_example_is_valid_product_configuration() -> None:
    env = _load_env_example(Path(".env.example"))

    report = validate_product_configuration(env)

    assert report.status == "PASS"


def test_product_doctor_configuration_only_uses_product_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key, value in _base_product_env().items():
        monkeypatch.setenv(key, value)

    report = build_product_doctor_report(evidence_dir=tmp_path, configuration_only=True)

    assert report["status"] == "PASS"
    assert report["configuration_only"] is True
    assert (tmp_path / "product_doctor_report.json").exists()
