from __future__ import annotations

import threading

from sentence_transformers import CrossEncoder

_MODEL_NAME = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
_encoder: CrossEncoder | None = None
_encoder_lock = threading.Lock()


def _get_encoder() -> CrossEncoder:
    global _encoder
    if _encoder is None:
        with _encoder_lock:
            if _encoder is None:  # double-checked locking — evita inicialização dupla sob concorrência
                _encoder = CrossEncoder(_MODEL_NAME)
    return _encoder


def precaquecer() -> None:
    """Carrega o cross-encoder em memória antes do primeiro request, eliminando a latência de 5–15s no startup."""
    _get_encoder()


def reranquear(query: str, candidatos: list[dict], top_k: int) -> list[dict]:
    if not candidatos:
        return candidatos

    encoder = _get_encoder()
    pares = [(query, c["texto"]) for c in candidatos]
    scores = encoder.predict(pares)

    ranqueados = sorted(
        zip(scores, candidatos),
        key=lambda x: x[0],
        reverse=True,
    )

    return [
        {**c, "rerank_score": float(s)}
        for s, c in ranqueados[:top_k]
    ]
