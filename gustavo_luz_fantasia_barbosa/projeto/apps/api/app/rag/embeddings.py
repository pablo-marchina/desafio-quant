import hashlib
import math
import re
import unicodedata
from functools import lru_cache
from collections.abc import Callable
from typing import Protocol

import requests

from app.config import Settings


TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_+\-.]+")


class EmbeddingProvider(Protocol):
    vector_size: int

    def embed(self, text: str) -> list[float]:
        ...


class HashEmbeddingProvider:
    """Local deterministic embeddings for an offline MVP.

    This is not a replacement for model embeddings, but it lets the full RAG
    path run without API keys. The interface is intentionally small so a real
    provider can replace it later.
    """

    def __init__(self, vector_size: int = 1536):
        self.vector_size = vector_size

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.vector_size
        normalized_text = unicodedata.normalize("NFKD", text.lower())
        normalized_text = "".join(
            character
            for character in normalized_text
            if not unicodedata.combining(character)
        )
        tokens = TOKEN_PATTERN.findall(normalized_text)

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.vector_size
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector

        return [value / norm for value in vector]


class OpenAIEmbeddingProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str = "text-embedding-3-small",
        vector_size: int = 1536,
        dimensions: int | None = None,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: int = 30,
    ):
        if not api_key:
            raise ValueError(
                "NVIDIA_RADAR_OPENAI_API_KEY precisa estar configurada para "
                "usar NVIDIA_RADAR_EMBEDDING_PROVIDER=openai."
            )

        self.api_key = api_key
        self.model = model
        self.vector_size = vector_size
        self.dimensions = dimensions
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def embed(self, text: str) -> list[float]:
        payload: dict[str, object] = {
            "model": self.model,
            "input": text,
            "encoding_format": "float",
        }
        if self.dimensions is not None:
            payload["dimensions"] = self.dimensions

        response = requests.post(
            f"{self.base_url}/embeddings",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()

        data = response.json().get("data") or []
        if not data:
            raise ValueError("OpenAI embeddings API nao retornou vetores.")

        vector = data[0].get("embedding")
        if not isinstance(vector, list):
            raise ValueError("Resposta da OpenAI embeddings API nao contem embedding valido.")

        if len(vector) != self.vector_size:
            raise ValueError(
                "Dimensao do embedding nao bate com a collection: "
                f"recebido={len(vector)}, esperado={self.vector_size}. "
                "Ajuste NVIDIA_RADAR_VECTOR_SIZE ou "
                "NVIDIA_RADAR_OPENAI_EMBEDDING_DIMENSIONS e reingira a collection."
            )

        return [float(value) for value in vector]


@lru_cache(maxsize=4)
def load_sentence_transformer(model_name: str, local_files_only: bool):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as error:
        raise ValueError(
            "sentence-transformers nao esta instalado. Rode "
            "'python -m pip install -r requirements.txt'."
        ) from error

    return SentenceTransformer(model_name, local_files_only=local_files_only)


class SentenceTransformersEmbeddingProvider:
    def __init__(
        self,
        *,
        model_name: str = "intfloat/multilingual-e5-small",
        vector_size: int = 384,
        text_prefix: str = "",
        local_files_only: bool = False,
    ):
        self.model_name = model_name
        self.vector_size = vector_size
        self.text_prefix = text_prefix
        self.local_files_only = local_files_only
        self.model = load_sentence_transformer(model_name, local_files_only)

    def embed(self, text: str) -> list[float]:
        encoded = self.model.encode(
            self.text_prefix + text,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        vector = encoded.tolist()

        if len(vector) != self.vector_size:
            raise ValueError(
                "Dimensao do embedding sentence-transformers nao bate com a "
                f"collection: recebido={len(vector)}, esperado={self.vector_size}. "
                "Ajuste NVIDIA_RADAR_VECTOR_SIZE e reingira a collection."
            )

        return [float(value) for value in vector]


class PrefixedEmbeddingProvider:
    def __init__(
        self,
        *,
        provider_factory: Callable[[str], EmbeddingProvider],
        query_prefix: str,
        passage_prefix: str,
    ):
        self.query_prefix = query_prefix
        self.passage_prefix = passage_prefix
        self.query_provider = provider_factory(query_prefix)
        self.passage_provider = provider_factory(passage_prefix)
        self.vector_size = self.query_provider.vector_size

    def embed(self, text: str) -> list[float]:
        return self.embed_query(text)

    def embed_query(self, text: str) -> list[float]:
        return self.query_provider.embed(text)

    def embed_passage(self, text: str) -> list[float]:
        return self.passage_provider.embed(text)


def create_embedding_provider(settings: Settings) -> EmbeddingProvider:
    provider = settings.embedding_provider.lower().strip()

    if provider == "hash":
        return HashEmbeddingProvider(vector_size=settings.vector_size)

    if provider == "openai":
        return OpenAIEmbeddingProvider(
            api_key=settings.openai_api_key or "",
            model=settings.openai_embedding_model,
            vector_size=settings.vector_size,
            dimensions=settings.openai_embedding_dimensions,
            base_url=settings.openai_base_url,
            timeout_seconds=settings.openai_timeout_seconds,
        )

    if provider in {"sentence_transformers", "sentence-transformers"}:
        return PrefixedEmbeddingProvider(
            provider_factory=lambda prefix: SentenceTransformersEmbeddingProvider(
                model_name=settings.sentence_transformers_model,
                vector_size=settings.vector_size,
                text_prefix=prefix,
                local_files_only=settings.sentence_transformers_local_files_only,
            ),
            query_prefix=settings.sentence_transformers_query_prefix,
            passage_prefix=settings.sentence_transformers_passage_prefix,
        )

    raise ValueError(
        "NVIDIA_RADAR_EMBEDDING_PROVIDER invalido. Use 'hash', 'openai' "
        "ou 'sentence_transformers'."
    )
