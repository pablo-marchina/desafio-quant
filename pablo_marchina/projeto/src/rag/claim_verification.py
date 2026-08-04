"""Claim Verification: extract claims from chunks, verify against evidence.

Uses NVIDIA LLM to:
1. Extract verifiable claims from each chunk
2. Score each claim for veracity / alignment with the query
3. Aggregate chunk-level claim scores
"""

from __future__ import annotations

from typing import Any

from src.rag.nvidia_client import NvidiaClient
from src.rag.schemas import ClaimVerificationConfig, RetrievalQuery, RetrievedContext

_NVIDIA_CLIENT: NvidiaClient | None = None


def _get_nvidia() -> NvidiaClient:
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        _NVIDIA_CLIENT = NvidiaClient()
    return _NVIDIA_CLIENT


_EXTRACT_PROMPT = """Extract the main claim from this document in one short sentence.

Document: {document}

Claim:"""

_VERIFY_PROMPT = """Verify if the claim below is supported by the query context.

Return ONLY a single number between 0.0 and 1.0:
0.0 = claim is completely unsupported
1.0 = claim is fully supported and directly relevant

Query: {query}
Claim: {claim}

Support score:"""


def verify_claims(
    contexts: list[RetrievedContext],
    query: RetrievalQuery | str,
    config: ClaimVerificationConfig | None = None,
) -> list[RetrievedContext]:
    """Verify claims in each chunk and adjust relevance scores.

    Chunks with verified claims get a score boost.
    Chunks with unsupported claims get a penalty.
    """
    cfg = config or ClaimVerificationConfig()
    if not cfg.enabled or not contexts:
        return contexts

    query_text = query if isinstance(query, str) else _build_query_text(query)
    nvidia = _get_nvidia()

    for ctx in contexts:
        claim = _extract_claim(nvidia, ctx.content[:512])
        if claim:
            support_score = _verify_claim(nvidia, query_text, claim)
            if support_score is not None:
                if support_score >= 0.5:
                    ctx.relevance_score = round(0.6 * ctx.relevance_score + 0.4 * support_score, 4)
                else:
                    ctx.relevance_score = round(ctx.relevance_score * support_score, 4)

    contexts.sort(key=lambda x: x.relevance_score, reverse=True)
    return contexts


def _extract_claim(nvidia: NvidiaClient, document: str) -> str | None:
    prompt = _EXTRACT_PROMPT.format(document=document[:400])
    reply = nvidia.llm_generate(prompt, max_tokens=64, temperature=0.01)
    return reply.strip() if reply else None


def _verify_claim(
    nvidia: NvidiaClient,
    query: str,
    claim: str,
) -> float | None:
    prompt = _VERIFY_PROMPT.format(query=query, claim=claim)
    reply = nvidia.llm_generate(prompt, max_tokens=10, temperature=0.01)
    if reply:
        try:
            return max(0.0, min(1.0, float(reply.strip().split()[0])))
        except (ValueError, IndexError):
            pass
    return None


def _build_query_text(query: RetrievalQuery) -> str:
    parts: list[str] = []
    if query.gap_type:
        parts.append(query.gap_type.replace("_", " "))
    if query.technology:
        parts.append(query.technology)
    if query.keywords:
        parts.extend(query.keywords)
    return " ".join(parts) if parts else ""


class ClaimVerification:
    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query = kwargs.get("query", "")
        config = kwargs.get("config")
        return verify_claims(contexts, query, config)
