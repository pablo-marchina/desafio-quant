from __future__ import annotations

from functools import lru_cache
from typing import Sequence

import numpy as np
from sentence_transformers import SentenceTransformer


MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384


@lru_cache(maxsize=1)
def _load_model() -> SentenceTransformer:
    return SentenceTransformer(MODEL_NAME)


def embed_text(text: str) -> list[float]:
    model = _load_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


def embed_batch(texts: Sequence[str]) -> list[list[float]]:
    if not texts:
        return []
    model = _load_model()
    vectors = model.encode(list(texts), normalize_embeddings=True)
    if isinstance(vectors, np.ndarray):
        return vectors.tolist()
    return [v.tolist() for v in vectors]
