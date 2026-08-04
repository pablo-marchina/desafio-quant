"""Testes do value object EmbeddingVector."""

import dataclasses

import pytest

from apps.api.src.modules.embeddings.domain.entities import EmbeddingVector
from apps.api.src.modules.embeddings.domain.exceptions import (
    InvalidEmbeddingDimensionError,
)


def test_creates_valid_vector() -> None:
    vector = EmbeddingVector(values=(0.1, 0.2, 0.3, 0.4), dimension=4, model_name="x")

    assert vector.dimension == 4
    assert len(vector.values) == 4


def test_raises_on_dimension_mismatch() -> None:
    with pytest.raises(InvalidEmbeddingDimensionError):
        EmbeddingVector(values=(0.1, 0.2), dimension=4, model_name="x")


def test_vector_is_immutable() -> None:
    vector = EmbeddingVector(values=(0.1,), dimension=1, model_name="x")

    with pytest.raises(dataclasses.FrozenInstanceError):
        vector.model_name = "y"  # type: ignore[misc]
