"""Tests for src.rag.embeddings — EmbeddingProvider abstraction."""

import builtins
from typing import Any

import pytest

from src.rag.embeddings import SentenceTransformerProvider


def test_sentence_transformer_provider_missing_dependency_mentions_rag_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "sentence_transformers":
            raise ImportError("missing sentence_transformers")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(ImportError, match=r'pip install -e "\.\[rag\]"'):
        SentenceTransformerProvider()


def test_sentence_transformer_provider_uses_new_dimension_method(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeModel:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

        def get_embedding_dimension(self) -> int:
            return 384

        def get_sentence_embedding_dimension(self) -> int:
            raise AssertionError("legacy dimension method should not be called")

    class FakeSentenceTransformers:
        SentenceTransformer = FakeModel

    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "sentence_transformers":
            return FakeSentenceTransformers
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    provider = SentenceTransformerProvider()

    assert provider.vector_size == 384


def test_sentence_transformer_provider_falls_back_to_legacy_dimension_method(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeLegacyModel:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

        def get_sentence_embedding_dimension(self) -> int:
            return 384

    class FakeSentenceTransformers:
        SentenceTransformer = FakeLegacyModel

    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "sentence_transformers":
            return FakeSentenceTransformers
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    provider = SentenceTransformerProvider()

    assert provider.vector_size == 384


def test_sentence_transformer_provider_defaults_to_384_when_dimension_is_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeNoneDimensionModel:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

        def get_embedding_dimension(self) -> None:
            return None

        def get_sentence_embedding_dimension(self) -> None:
            return None

    class FakeSentenceTransformers:
        SentenceTransformer = FakeNoneDimensionModel

    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "sentence_transformers":
            return FakeSentenceTransformers
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    provider = SentenceTransformerProvider()

    assert provider.vector_size == 384
