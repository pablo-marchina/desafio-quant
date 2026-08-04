"""Deterministic bridge from raw_evidence_candidates to structured evidence/claims/profile.

No LLM, no Qdrant, no scraping, no internet. Uses the real rule-based
``src.extraction.extractor.extract_profile`` under the hood.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
import uuid
from datetime import UTC, datetime
from typing import Any

from src.extraction.schemas import ConfidenceLevel, Evidence, SourceType, StartupProfile
from src.scraping.source_policy import source_quality_score

_EXTRACTION_METHOD = "deterministic_pattern"
_SIGNAL_SEPARATOR_RE = re.compile(r"[^a-z0-9]+")

_NVIDIA_RELEVANCE_KEYWORDS: list[str] = [
    "nvidia",
    "cuda",
    "gpu",
    "tensorrt",
    "triton",
    "rapids",
    "cudf",
    "cuml",
    "nemotron",
    "nemotron",
    "nemo",
    "omniverse",
    "isaac",
    "clar",
    "morpheus",
    "rive",
    "ai enterprise",
]


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _normalize_signal_text(text: str) -> str:
    """Normalize internal classifier text while preserving raw citation text.

    Gap and workload taxonomies use canonical ASCII phrases. Real sources use
    punctuation, hyphens, and Portuguese diacritics (for example,
    ``computer-vision`` and ``visão computacional``). Normalizing only the
    classifier field makes these equivalent without altering quotes or source
    excerpts shown to users.
    """
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return " ".join(_SIGNAL_SEPARATOR_RE.sub(" ", ascii_text.casefold()).split())


def _detect_nvidia_terms(text: str) -> list[str]:
    text_lower = text.lower()
    found: list[str] = []
    for kw in _NVIDIA_RELEVANCE_KEYWORDS:
        if kw in text_lower:
            found.append(kw)
    return found


def _build_evidence_item(
    source_candidate: dict[str, Any],
    profile: StartupProfile,
    source_type: SourceType,
) -> dict[str, Any]:
    text: str = source_candidate.get("text", "")
    source_url: str = source_candidate.get("source_url") or source_candidate.get("url", "")
    source_id: str = source_candidate.get("source_id", "")
    collected_at_raw: str = source_candidate.get("collected_at") or source_candidate.get("fetched_at") or ""

    now_ts: str = datetime.now(UTC).isoformat()
    extracted_at: str = collected_at_raw if collected_at_raw else now_ts

    snippet = text[:300] if text else ""
    txt_hash = _content_hash(text) if text else ""
    conf = profile.confidence_score

    st_value: str = source_type.value if isinstance(source_type, SourceType) else str(source_type)
    score = source_quality_score(source_type)
    from src.extraction.schemas import ConfidenceLevel

    confidence_level = ConfidenceLevel.from_score(conf).value
    summary = profile.product_summary if profile.product_summary != "Not verified" else profile.description
    claim_text = f"{profile.startup_name}: {summary or snippet}"[:1000]
    quote = text[:1200] if text else snippet

    factuality: str = "observed" if text else "unknown"
    primary_source = profile.sources[0] if profile.sources else None
    canonical_claim = (
        primary_source.claim
        if primary_source is not None and primary_source.claim
        else f"{profile.startup_name} shows evidence of {', '.join(profile.ai_signals[:3]) or 'AI activity'}."
    )
    canonical_quote = (
        primary_source.quote_or_evidence
        if primary_source is not None and primary_source.quote_or_evidence
        else snippet
    )
    canonical_confidence = (
        primary_source.confidence.value
        if primary_source is not None and hasattr(primary_source.confidence, "value")
        else ConfidenceLevel.from_score(conf).value
    )
    canonical_collected_at = (
        primary_source.collected_at.isoformat()
        if primary_source is not None
        else extracted_at
    )
    upstream_evidence_id = source_candidate.get("evidence_id") or source_candidate.get("id")

    item: dict[str, Any] = {
        "evidence_id": str(uuid.uuid4()),
        "claim": claim_text,
        "source_id": source_id,
        "source_url": source_url,
        "url": source_url,
        "source_type": st_value,
        "quote_or_evidence": quote,
        "confidence": confidence_level,
        "title": profile.startup_name,
        "snippet": snippet,
        "extracted_text_hash": txt_hash,
        "collected_at": canonical_collected_at,
        "extracted_at": now_ts,
        "evidence_type": "extracted",
        "source_quality_score": score,
        "extraction_confidence": conf,
        "confidence_calibration_decision_id": "extraction.confidence_formula_base",
        "factuality_status": factuality,
        "supports_claim_ids": [],
        "text": _normalize_signal_text(text),
        "raw_text": text,
        "startup_name": profile.startup_name,
        "ai_signals": profile.ai_signals,
    }
    return item


def _build_claim(
    evidence_item: dict[str, Any],
    evidence_source: Evidence,
    idx: int,
) -> dict[str, Any]:
    source_type_str: str = evidence_item.get("source_type", "unknown")
    is_critical: bool = source_type_str in ("official_site", "official_website")

    claim_type: str = "unknown"
    claim_text: str = evidence_source.claim or ""
    ct_lower = claim_text.lower()
    if "ai" in ct_lower or "signal" in ct_lower:
        claim_type = "ai_signal"
    elif "founder" in ct_lower:
        claim_type = "founder_mention"
    elif "customer" in ct_lower:
        claim_type = "customer_mention"
    elif "funding" in ct_lower:
        claim_type = "funding_or_traction"
    elif "tech stack" in ct_lower or "technical" in ct_lower:
        claim_type = "technical_signal"
    elif "description" in ct_lower or "company" in ct_lower:
        claim_type = "company_description"

    conf_value: float = 0.5
    if evidence_source.confidence:
        conf_map = {
            ConfidenceLevel.HIGH: 0.9,
            ConfidenceLevel.MEDIUM: 0.6,
            ConfidenceLevel.LOW: 0.3,
        }
        conf_value = conf_map.get(evidence_source.confidence, 0.5)

    factuality: str = "inferred"
    quote = evidence_source.quote_or_evidence or ""
    if quote and len(quote) > 20:
        factuality = "observed"

    claim_id: str = str(uuid.uuid4())

    return {
        "claim_id": claim_id,
        "claim_text": claim_text,
        "claim_type": claim_type,
        "criticality": "critical" if is_critical else "normal",
        "support_status": "supported",
        "supporting_evidence_ids": [evidence_item["evidence_id"]],
        "confidence": conf_value,
        "confidence_calibration_decision_id": "extraction.confidence_formula_base",
        "extraction_method": _EXTRACTION_METHOD,
        "factuality_status": factuality,
    }


def _merge_profiles(profiles: list[StartupProfile]) -> dict[str, Any]:
    if not profiles:
        return {}
    merged: dict[str, Any] = {}
    all_ai_signals: list[str] = []
    all_tech_terms: list[str] = []
    all_funding: list[str] = []
    source_coverage: dict[str, int] = {}
    conf_sum: float = 0.0
    all_customers: list[str] = []
    all_founders: list[str] = []

    for p in profiles:
        if p.startup_name and p.startup_name != "Not verified":
            merged["startup_name"] = p.startup_name
        if str(p.website) and str(p.website) != "Not verified":
            merged["website_url"] = str(p.website)
            merged["website"] = str(p.website)
        if p.country:
            merged["country"] = p.country
        if p.sector:
            merged["sector"] = p.sector
        if p.description and p.description != "Not verified":
            merged["description"] = p.description
        if p.product_summary and p.product_summary != "Not verified":
            merged["product_summary"] = p.product_summary
        all_ai_signals.extend(p.ai_signals)
        all_tech_terms.extend(p.tech_stack_signals)
        all_funding.extend(p.funding_signals)
        all_customers.extend(p.customers)
        all_founders.extend(p.founders)
        for src in p.sources:
            st_val = src.source_type.value if hasattr(src.source_type, "value") else str(src.source_type)
            source_coverage[st_val] = source_coverage.get(st_val, 0) + 1
        conf_sum += p.confidence_score

    merged["ai_signals"] = list(set(all_ai_signals))
    merged["tech_stack_signals"] = list(set(all_tech_terms))
    merged["funding_signals"] = list(set(all_funding))
    merged["customers"] = list(set(all_customers))
    merged["founders"] = list(set(all_founders))

    merged["detected_domains"] = list(set(all_tech_terms))
    merged["detected_products"] = (
        [p for p in [profiles[0].product_summary] if p and p != "Not verified"] if profiles else []
    )
    merged["detected_ai_signals"] = list(set(all_ai_signals))
    merged["detected_technical_terms"] = list(set(all_tech_terms))

    all_text = " ".join(
        str(p.description) + " " + str(p.product_summary)
        for p in profiles
        if str(p.description) != "Not verified" or str(p.product_summary) != "Not verified"
    )
    merged["detected_nvidia_relevance_terms"] = _detect_nvidia_terms(all_text) if all_text else []
    merged["detected_funding_or_traction_signals"] = list(set(all_funding))
    merged["source_coverage_by_type"] = source_coverage
    merged["profile_confidence"] = round(conf_sum / len(profiles), 4) if profiles else 0.1
    merged["profile_confidence_calibration_decision_id"] = "extraction.confidence_formula_base"

    merged["confidence_score"] = merged["profile_confidence"]
    if "startup_name" not in merged:
        merged["startup_name"] = "Not verified"
    if "website_url" not in merged:
        merged["website_url"] = ""
    merged["sources"] = [s.model_dump(mode="json") for p in profiles for s in p.sources]
    return merged


def extract_profiles_from_candidates(
    raw_evidence_candidates: list[dict[str, Any]],
    startup_name: str | None,
    startup_id: str | None,
    run_id: str,
) -> dict[str, Any]:
    """Bridge from raw_evidence_candidates → structured evidence/claims/profile.

    Returns a dict with keys:
        evidence_items, claims, startup_profile, raw_evidence,
        extraction_metrics, errors
    """
    from src.extraction.extractor import extract_profile as _run_extraction

    evidence_items: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    raw_evidence: list[dict[str, Any]] = []
    profiles_raw: list[StartupProfile] = []
    errors: list[str] = []

    seen_hashes: set[str] = set()
    duplicate_count = 0
    empty_count = 0

    extraction_attempt_count = len(raw_evidence_candidates)
    extraction_success_count = 0
    extraction_failure_count = 0

    source_type_aliases: dict[str, SourceType] = {
        "official_website": SourceType.OFFICIAL_SITE,
    }

    for candidate in raw_evidence_candidates:
        text: str = candidate.get("text", "") or ""
        source_url: str = candidate.get("source_url") or candidate.get("url", "") or ""

        if not text.strip():
            empty_count += 1
            extraction_failure_count += 1
            continue

        txt_hash = _content_hash(text)
        if txt_hash in seen_hashes:
            duplicate_count += 1
            extraction_failure_count += 1
            continue
        seen_hashes.add(txt_hash)

        raw_st = candidate.get("source_type") or candidate.get("source_category", "")
        source_type: SourceType = SourceType.DIRECTORY
        if isinstance(raw_st, str) and raw_st:
            if raw_st in source_type_aliases:
                source_type = source_type_aliases[raw_st]
            else:
                try:
                    source_type = SourceType(raw_st)
                except ValueError:
                    source_type = SourceType.DIRECTORY

        try:
            profile: StartupProfile = _run_extraction(
                clean_text=text,
                url=source_url,
                startup_name_hint=startup_name,
                source_type=source_type,
            )
            profiles_raw.append(profile)
            extraction_success_count += 1

            ev_item = _build_evidence_item(candidate, profile, source_type)
            evidence_items.append(ev_item)

            for src in profile.sources:
                claim_dict = _build_claim(ev_item, src, len(claims))
                claim_dict["supporting_evidence_ids"] = [ev_item["evidence_id"]]
                claims.append(claim_dict)
                ev_item["supports_claim_ids"].append(claim_dict["claim_id"])

                raw_evidence.append(src.model_dump(mode="json"))

        except Exception as exc:
            extraction_failure_count += 1
            errors.append(f"extract_profile failed for {source_url}: {exc}")

    startup_profile: dict[str, Any] = _merge_profiles(profiles_raw) if profiles_raw else {}
    if startup_id:
        startup_profile["startup_id"] = startup_id
    if run_id:
        startup_profile["run_id"] = run_id

    source_type_coverage: dict[str, int] = {}
    for ev in evidence_items:
        st = ev.get("source_type", "unknown")
        source_type_coverage[st] = source_type_coverage.get(st, 0) + 1

    total_fields = 8
    filled = sum(
        1
        for f in [
            startup_profile.get("detected_ai_signals"),
            startup_profile.get("detected_technical_terms"),
            startup_profile.get("detected_funding_or_traction_signals"),
            startup_profile.get("detected_nvidia_relevance_terms"),
            startup_profile.get("detected_products"),
            startup_profile.get("detected_domains"),
            startup_profile.get("source_coverage_by_type"),
            startup_profile.get("profile_confidence", 0) > 0,
        ]
        if f
    )

    average_extraction_confidence = (
        sum(ev.get("extraction_confidence", 0) for ev in evidence_items) / len(evidence_items)
        if evidence_items
        else 0.0
    )

    extraction_metrics: dict[str, Any] = {
        "raw_candidates_count": len(raw_evidence_candidates),
        "extraction_attempt_count": extraction_attempt_count,
        "extraction_success_count": extraction_success_count,
        "extraction_failure_count": extraction_failure_count,
        "evidence_items_count": len(evidence_items),
        "claims_count": len(claims),
        "empty_content_count": empty_count,
        "duplicate_content_count": duplicate_count,
        "source_type_coverage": source_type_coverage,
        "extraction_success_rate": (
            round(extraction_success_count / extraction_attempt_count, 4) if extraction_attempt_count > 0 else 0.0
        ),
        "profile_field_coverage": round(filled / total_fields, 4),
        "average_extraction_confidence": round(average_extraction_confidence, 4),
    }

    return {
        "evidence_items": evidence_items,
        "claims": claims,
        "startup_profile": startup_profile,
        "raw_evidence": raw_evidence,
        "extraction_metrics": extraction_metrics,
        "errors": errors,
    }


def extract_profiles(
    raw_evidence_candidates: list[dict[str, Any]],
    startup_name: str | None = None,
    startup_id: str | None = None,
    run_id: str = "unknown",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    """Backward-compatible tuple wrapper around ``extract_profiles_from_candidates``."""
    result = extract_profiles_from_candidates(
        raw_evidence_candidates=raw_evidence_candidates,
        startup_name=startup_name,
        startup_id=startup_id,
        run_id=run_id,
    )
    return (
        list(result.get("evidence_items", [])),
        list(result.get("claims", [])),
        dict(result.get("startup_profile", {})),
        list(result.get("raw_evidence", [])),
    )
