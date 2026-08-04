from __future__ import annotations

import re

from radar.graph.state import RadarState
from radar.schemas import EvidenceClaim, EvidenceValidationReport


MINIMUM_CLAIMS = 2
MINIMUM_AI_CLAIMS = 1
MINIMUM_CONFIDENCE = 0.5

AI_EVIDENCE_PATTERNS = (
    re.compile(r"\b[Aa][Ii]\b"),                            # standalone "AI"
    re.compile(r"\bintelig[eê]ncia\s+artificial\b"),        # IA em português
    re.compile(r"\bartificial\s+intelligence\b"),            # full English
    re.compile(r"\bllm\b|\bllms\b", re.IGNORECASE),
    re.compile(r"\bmachine\s+learning\b", re.IGNORECASE),
    re.compile(r"\bdeep\s+learning\b", re.IGNORECASE),
    re.compile(r"\bneural\s+network", re.IGNORECASE),
    re.compile(r"\bGPT\b|\bgpt-|\bchatgpt\b", re.IGNORECASE),
    re.compile(r"\bfine[ -]?tun(?:ing|ed)\b", re.IGNORECASE),
    re.compile(r"\bopenai\b", re.IGNORECASE),
    re.compile(r"\btransformers?\b", re.IGNORECASE),
    re.compile(r"\bword2vec\b|\bbert\b|\blstm\b", re.IGNORECASE),
)


def _has_real_ai_evidence(text: str) -> bool:
    return any(p.search(text) for p in AI_EVIDENCE_PATTERNS)


def validate_evidence(state: RadarState) -> EvidenceValidationReport:
    claims = state.get("claims", [])
    sources = state.get("sources", [])
    source_by_id = {source.id: source for source in sources}

    supporting_claims = [
        claim
        for claim in claims
        if claim.confidence >= MINIMUM_CONFIDENCE and claim.source_document_id in source_by_id
    ]

    supporting_ids = [claim.id for claim in supporting_claims]
    supporting_urls = {str(source_by_id[claim.source_document_id].url) for claim in supporting_claims}
    ai_supporting_claims = [claim for claim in supporting_claims if claim.claim_type == "ai_usage"]

    validated_ai_claims = [
        c for c in ai_supporting_claims if _has_real_ai_evidence(c.text)
    ]
    false_positive_ai_claims = [
        c for c in ai_supporting_claims if not _has_real_ai_evidence(c.text)
    ]

    has_minimum_evidence = (
        len(supporting_ids) >= MINIMUM_CLAIMS
        and len(supporting_urls) >= MINIMUM_CLAIMS
        and len(validated_ai_claims) >= MINIMUM_AI_CLAIMS
    )

    return EvidenceValidationReport(
        has_minimum_evidence=has_minimum_evidence,
        source_quality="medium" if has_minimum_evidence else "weak",
            supporting_evidence_ids=[c.id for c in validated_ai_claims] + [c.id for c in supporting_claims if c.claim_type != "ai_usage"],
        conflicts=[],
        caveats=_build_caveats(
            supporting_ids=supporting_ids,
            supporting_urls=supporting_urls,
            validated_ai_claims=validated_ai_claims,
            false_positive_ai_claims=false_positive_ai_claims,
        ),
        requires_human_review=not has_minimum_evidence,
    )


def _build_caveats(
    *,
    supporting_ids: list[str],
    supporting_urls: set[str],
    validated_ai_claims: list[EvidenceClaim],
    false_positive_ai_claims: list[EvidenceClaim],
) -> list[str]:
    caveats: list[str] = []
    if len(supporting_ids) < MINIMUM_CLAIMS or len(supporting_urls) < MINIMUM_CLAIMS:
        caveats.append("Need at least two independent public evidence claims before recommendations.")
    if len(validated_ai_claims) < MINIMUM_AI_CLAIMS:
        caveats.append("Need at least one validated AI usage claim before recommendations.")
    if false_positive_ai_claims:
        caveats.append(
            f"Rejeitadas {len(false_positive_ai_claims)} claim(s) de IA que não continham "
            f"evidência semântica real (ex: 'ai' como substring em palavra não relacionada)."
        )
    return caveats
