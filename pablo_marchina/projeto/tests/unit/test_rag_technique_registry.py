from __future__ import annotations

from src.rag.technique_registry import load_enabled_technique_names, validate_enabled_techniques


def test_enabled_rag_techniques_are_importable() -> None:
    names = load_enabled_technique_names()

    assert names
    assert "multi_query" in names
    assert "colbert_reranking" in names
    assert "cross_encoder" in names
    assert validate_enabled_techniques() == []
