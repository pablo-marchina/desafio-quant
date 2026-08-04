"""NVIDIA Triton-backed reranking for the official RAG runtime path.

The production contract is intentionally strict: in APP_MODE=product the Triton
reranker must be configured and reachable. In development/test mode the function
returns the input contexts with explicit metadata when Triton is not configured,
so local unit tests can run without external services.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from src.rag.schemas import RetrievalQuery, RetrievedContext


class TritonRerankerUnavailable(RuntimeError):
    """Raised when the required Triton reranker cannot be used."""


def triton_rerank_contexts(
    contexts: list[RetrievedContext],
    query: RetrievalQuery,
    *,
    timeout_seconds: float | None = None,
) -> tuple[list[RetrievedContext], dict[str, Any]]:
    """Rerank contexts through an NVIDIA Triton inference endpoint.

    The endpoint is expected to accept a JSON payload compatible with Triton's
    HTTP v2 ``/infer`` route. The payload includes text pairs and prior scores.
    The parser accepts common response shapes: ``outputs[0].data`` or ``scores``.
    """

    enabled = os.getenv("TRITON_RERANKER_ENABLED", "true").lower() in {"1", "true", "yes"}
    required = os.getenv("TRITON_RERANKER_REQUIRED", os.getenv("APP_MODE", "dev") == "product" and "true" or "false").lower() in {"1", "true", "yes"}
    app_mode = os.getenv("APP_MODE", "dev")
    url = os.getenv("TRITON_RERANKER_URL", "").strip()

    metadata: dict[str, Any] = {
        "enabled": enabled,
        "required": required,
        "provider": "nvidia_triton",
        "model": os.getenv("TRITON_RERANKER_MODEL", "nvidia-reranker"),
        "called": False,
        "fallback_used": False,
    }

    if not contexts or not enabled:
        metadata["skipped_reason"] = "disabled_or_empty"
        return contexts, metadata

    if not url:
        metadata["fallback_used"] = True
        metadata["skipped_reason"] = "TRITON_RERANKER_URL_not_configured"
        if required or app_mode == "product":
            raise TritonRerankerUnavailable("TRITON_RERANKER_URL is required for production reranking")
        return contexts, metadata

    query_text = _query_text(query)
    text_input_name = os.getenv("TRITON_RERANKER_TEXT_INPUT_NAME", "documents")
    query_input_name = os.getenv("TRITON_RERANKER_QUERY_INPUT_NAME", "query")
    score_input_name = os.getenv("TRITON_RERANKER_SCORE_INPUT_NAME", "scores")
    # Default runtime contract matches the bundled Triton Python backend under
    # models/cross_encoder: one query tensor plus a [N, 1] document tensor.
    # The legacy text_pairs contract remains available by setting
    # TRITON_RERANKER_TEXT_INPUT_NAME=text_pairs.
    if text_input_name == "text_pairs":
        text_pairs = [[query_text, c.content] for c in contexts]
        prior_scores = [float(c.relevance_score) for c in contexts]
        payload = {
            "inputs": [
                {"name": text_input_name, "shape": [len(text_pairs), 2], "datatype": "BYTES", "data": text_pairs},
                {"name": score_input_name, "shape": [len(prior_scores)], "datatype": "FP32", "data": prior_scores},
            ],
            "parameters": {"query": query_text},
        }
    else:
        documents = [[c.content] for c in contexts]
        payload = {
            "inputs": [
                {"name": query_input_name, "shape": [1], "datatype": "BYTES", "data": [query_text]},
                {"name": text_input_name, "shape": [len(documents), 1], "datatype": "BYTES", "data": documents},
            ],
        }

    timeout = timeout_seconds or float(os.getenv("TRITON_RERANKER_TIMEOUT_SECONDS", "8"))
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            body = response.json()
        scores = _extract_scores(body, len(contexts))
    except Exception as exc:
        metadata["fallback_used"] = True
        metadata["error"] = str(exc)
        if required or app_mode == "product":
            raise TritonRerankerUnavailable(f"Triton reranker failed: {exc}") from exc
        return contexts, metadata

    reranked: list[tuple[RetrievedContext, float]] = []
    for ctx, score in zip(contexts, scores, strict=False):
        clone = ctx.model_copy(deep=True)
        clone.relevance_score = round(max(0.0, min(1.0, float(score))), 4)
        reranked.append((clone, clone.relevance_score))
    reranked.sort(key=lambda item: item[1], reverse=True)
    metadata.update({"called": True, "context_count": len(reranked), "fallback_used": False})
    return [ctx for ctx, _ in reranked], metadata


def _query_text(query: RetrievalQuery) -> str:
    terms: list[str] = []
    if query.gap_type:
        terms.append(query.gap_type.replace("_", " "))
    if query.technology:
        terms.append(query.technology)
    terms.extend(query.keywords)
    return " ".join(dict.fromkeys(t for t in terms if t)).strip() or "NVIDIA technology recommendation"


def _extract_scores(body: dict[str, Any], expected_count: int) -> list[float]:
    if isinstance(body.get("scores"), list):
        scores = body["scores"]
    else:
        outputs = body.get("outputs") or []
        if not outputs:
            raise ValueError("Triton response did not include outputs")
        data = outputs[0].get("data") if isinstance(outputs[0], dict) else None
        if not isinstance(data, list):
            raise ValueError("Triton response output did not include score data")
        scores = data
    if len(scores) < expected_count:
        raise ValueError(f"Triton returned {len(scores)} scores for {expected_count} contexts")
    return [float(s) for s in scores[:expected_count]]


class TritonReranker:
    """Technique loader facade for NVIDIA Triton reranking."""
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query = kwargs.get("retrieval_query") or kwargs.get("query")
        if not isinstance(query, RetrievalQuery):
            return contexts
        reranked, _ = triton_rerank_contexts(contexts, query)
        return reranked
