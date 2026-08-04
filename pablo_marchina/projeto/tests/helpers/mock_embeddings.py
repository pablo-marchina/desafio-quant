"""Mock embedding provider for tests only.

Generates reproducible pseudo-embeddings using MD5 hash as seed.
"""

from __future__ import annotations

import hashlib
import math
import warnings


def _text_to_seed(text: str) -> int:
    h = hashlib.md5(text.encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def _pseudo_embedding(seed: int, size: int) -> list[float]:
    result: list[float] = []
    for i in range(size):
        val = math.sin(seed + i * 0.1) * math.cos(seed * 0.01 + i)
        result.append(round(val, 6))
    norm = math.sqrt(sum(x * x for x in result)) or 1.0
    return [round(x / norm, 6) for x in result]


class MockEmbeddingProvider:
    """Deterministic pseudo-embedding provider for tests only.

    Generates reproducible embeddings using MD5 hash as seed.
    No external dependencies, no model downloads.
    """

    def __init__(self, vector_size: int = 4) -> None:
        self.vector_size = vector_size

    def embed(self, text: str) -> list[float]:
        seed = _text_to_seed(text)
        return _pseudo_embedding(seed, self.vector_size)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]
