"""Validate raw evidence using the evidence validation service."""

from __future__ import annotations

from typing import Any


def validate_evidence(
    raw_evidence: list[dict[str, Any]],
    evidence_items: list[dict[str, Any]],
) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    from src.extraction.schemas import Evidence
    from src.validation.evidence_validator import validate_evidence_batch

    claims: list[str] = []
    errors: list[str] = []

    if not raw_evidence:
        return claims, evidence_items, [], errors

    try:
        evidence_objects = [Evidence.model_validate(ev) for ev in raw_evidence]
    except Exception as exc:
        return claims, evidence_items, [], [f"Failed to deserialize raw_evidence: {exc}"]

    validated = validate_evidence_batch(evidence_objects)

    claims = [f"[{v.evidence_kind.value}] {v.claim}: {v.quote_or_evidence}" for v in validated]

    kind_rank: dict[str, int] = {
        "fact": 0,
        "strong_inference": 1,
        "weak_inference": 2,
        "hypothesis": 3,
        "unverified": 4,
    }
    url_meta: dict[str, dict[str, str]] = {}
    for v in validated:
        url = str(v.source_url).rstrip("/")
        current = url_meta.get(url)
        rank = kind_rank.get(v.evidence_kind.value, 99)
        if current is None or rank < kind_rank.get(current.get("evidence_kind", ""), 99):
            url_meta[url] = {
                "evidence_kind": v.evidence_kind.value,
                "validated_confidence": v.confidence.value,
            }

    items_with_meta: list[dict[str, Any]] = []
    for item in evidence_items:
        enriched: dict[str, Any] = dict(item)
        meta = url_meta.get(item.get("url", "").rstrip("/"))
        if meta:
            enriched["evidence_kind"] = meta["evidence_kind"]
            enriched["validated_confidence"] = meta["validated_confidence"]
        items_with_meta.append(enriched)

    validated_evidence_serialized = [v.model_dump(mode="json") for v in validated]
    return claims, items_with_meta, validated_evidence_serialized, errors
