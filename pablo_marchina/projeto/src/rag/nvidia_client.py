"""Shared NVIDIA API client for LLM, embeddings, and reranker.

Uses NVIDIA AI API at integrate.api.nvidia.com for LLM and embeddings,
and ai.api.nvidia.com for the reranker. All calls are optional — returns
None on failure so callers degrade gracefully.
"""

from __future__ import annotations

import math
import os
from typing import Any, cast

import httpx

_NIM_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
_EMBED_URL = "https://integrate.api.nvidia.com/v1/embeddings"
_RERANK_URL = "https://ai.api.nvidia.com/v1/retrieval/nvidia/reranking"


class NvidiaClient:
    """HTTP client for NVIDIA AI API endpoints.

    Lazily loads the API key from the NVIDIA_API_KEY env var.
    Every method returns None on failure so callers fall back gracefully.
    """

    def __init__(self, timeout: int = 30) -> None:
        self._client = httpx.Client(timeout=timeout)
        self._api_key: str | None = None

    @property
    def api_key(self) -> str | None:
        if self._api_key is None:
            self._api_key = os.environ.get("NVIDIA_API_KEY")
        return self._api_key

    def _headers(self) -> dict[str, str]:
        key = self.api_key
        if not key:
            return {}
        return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    # ------------------------------------------------------------------
    # LLM
    # ------------------------------------------------------------------

    def llm_generate(
        self,
        prompt: str,
        model: str = "meta/llama-3.1-8b-instruct",
        max_tokens: int = 128,
        temperature: float = 0.01,
    ) -> str | None:
        """Call NVIDIA NIM chat completion.

        Returns the assistant reply text, or None on failure.
        """
        headers = self._headers()
        if not headers:
            return None
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        try:
            resp = self._client.post(_NIM_URL, json=payload, headers=headers)
            if resp.status_code != 200:
                return None
            body = resp.json()
            return cast(str, body["choices"][0]["message"]["content"])
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------

    def embed(
        self,
        text: str,
        model: str = "nvidia/nv-embedqa-e5-v5",
        input_type: str = "query",
    ) -> list[float] | None:
        """Generate embedding for a single text via NVIDIA API.

        Returns a list of floats, or None on failure.
        """
        headers = self._headers()
        if not headers:
            return None
        payload = {"model": model, "input": text, "input_type": input_type}
        try:
            resp = self._client.post(_EMBED_URL, json=payload, headers=headers)
            if resp.status_code != 200:
                return None
            body = resp.json()
            return cast(list[float], body["data"][0]["embedding"])
        except Exception:
            return None

    def embed_batch(
        self,
        texts: list[str],
        model: str = "nvidia/nv-embedqa-e5-v5",
        input_type: str = "passage",
    ) -> list[list[float]] | None:
        headers = self._headers()
        if not headers:
            return None
        payload = {"model": model, "input": texts, "input_type": input_type}
        try:
            resp = self._client.post(_EMBED_URL, json=payload, headers=headers)
            if resp.status_code != 200:
                return None
            body = resp.json()
            return [item["embedding"] for item in body["data"]]
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Reranker
    # ------------------------------------------------------------------

    def rerank(
        self,
        query: str,
        passages: list[str],
        model: str = "nvidia/rerank-qa-mistral-4b",
    ) -> list[tuple[int, float]] | None:
        """Rerank passages against a query via NVIDIA reranker API.

        Returns a list of (index, logit) sorted by relevance descending,
        or None on failure.
        """
        headers = self._headers()
        if not headers:
            return None
        payload = {
            "model": model,
            "query": {"text": query},
            "passages": [{"text": p} for p in passages],
        }
        try:
            resp = self._client.post(_RERANK_URL, json=payload, headers=headers)
            if resp.status_code != 200:
                return None
            body = resp.json()
            rankings = body.get("rankings", [])
            return [(r["index"], self._sigmoid(float(r.get("logit", 0.0)))) for r in rankings]
        except Exception:
            return None

    @staticmethod
    def _sigmoid(x: float) -> float:
        return 1.0 / (1.0 + math.exp(-max(min(x, 20.0), -20.0)))

    def close(self) -> None:
        self._client.close()
