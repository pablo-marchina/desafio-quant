"""Claim ledger service for evidence-linked claim generation and coverage."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from src.database.models import AnalysisRun, ClaimRecord, ScoreRecord
from src.quantitative.params import CONFIDENCE_FLOAT_MAP
from src.repositories.claim import ClaimRepository
from src.services.product.claim_constants import (
    ClaimType,
    SupportLevel,
)


def _confidence_to_float(confidence: str) -> float:
    return CONFIDENCE_FLOAT_MAP.get(confidence, 0.0)


def _calculate_support_level(
    evidence_refs: list[dict[str, Any]],
    confidence: str,
) -> str:
    if not evidence_refs:
        return SupportLevel.unsupported.value
    conf_float = _confidence_to_float(confidence)
    if conf_float >= 0.8:
        return SupportLevel.strong.value
    if conf_float >= 0.5:
        return SupportLevel.medium.value
    return SupportLevel.weak.value


def _normalize_evidence_refs(
    items: list[Any],
    refs_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        raw_id = item.get("id") or item.get("evidence_id")
        if raw_id is not None and str(raw_id) in refs_by_id:
            refs.append(refs_by_id[str(raw_id)])
            continue
        if item.get("source_url") or item.get("claim") or item.get("chunk_id"):
            refs.append(
                {
                    key: item[key]
                    for key in (
                        "evidence_id",
                        "chunk_id",
                        "source_id",
                        "source_url",
                        "title",
                        "claim",
                        "confidence",
                        "evidence_kind",
                        "matched_gap",
                        "matched_technology",
                    )
                    if key in item and item[key] not in (None, "")
                }
            )
    return refs


class ClaimLedgerService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = ClaimRepository(session)

    def build_claims_from_existing_records(
        self,
        analysis_run: AnalysisRun,
    ) -> list[dict[str, Any]]:
        claims: list[dict[str, Any]] = []
        startup_id = analysis_run.startup_id
        run_id = analysis_run.id

        refs_by_id: dict[str, dict[str, Any]] = {}
        for ev in analysis_run.startup.evidence if analysis_run.startup else []:
            refs_by_id[ev.id] = {
                "evidence_id": ev.id,
                "source_url": ev.source_url,
                "claim": ev.claim,
                "confidence": ev.confidence,
            }

        for ev in analysis_run.startup.evidence if analysis_run.startup else []:
            support = _calculate_support_level(
                [{"evidence_id": ev.id, "source_url": ev.source_url, "claim": ev.claim}],
                ev.confidence,
            )
            claims.append(
                {
                    "startup_id": startup_id,
                    "analysis_run_id": run_id,
                    "claim_text": ev.claim,
                    "claim_type": (
                        ClaimType.ai_native_claim.value
                        if ev.evidence_kind in ("fact", "inferred")
                        else ClaimType.technical_stack_claim.value
                    ),
                    "support_level": support,
                    "confidence": ev.confidence,
                    "evidence_refs": [refs_by_id.get(ev.id, {})],
                    "used_in_score": True,
                    "used_in_gap": True,
                    "used_in_mapping": True,
                    "used_in_brief": True,
                    "metadata": {"evidence_kind": ev.evidence_kind},
                }
            )

        score_map: dict[str, ScoreRecord] = {}
        for s in analysis_run.scores:
            score_map[s.score_type] = s
            score_type_to_claim = {
                "defensibility": ClaimType.defensibility_claim.value,
                "inception_fit": ClaimType.nvidia_fit_claim.value,
                "production_readiness": ClaimType.production_readiness_claim.value,
            }
            claim_type = score_type_to_claim.get(s.score_type)
            if claim_type:
                evidence_refs = _normalize_evidence_refs(
                    list(s.components_json.get("evidence_used", [])),
                    refs_by_id,
                )
                support = _calculate_support_level(evidence_refs, s.confidence)
                missing = s.missing_evidence_json or []
                claims.append(
                    {
                        "startup_id": startup_id,
                        "analysis_run_id": run_id,
                        "claim_text": (f"{s.score_type} score = {s.value} (confidence: {s.confidence})"),
                        "claim_type": claim_type,
                        "support_level": support,
                        "confidence": s.confidence,
                        "evidence_refs": evidence_refs,
                        "used_in_score": True,
                        "used_in_gap": True,
                        "used_in_mapping": True,
                        "used_in_brief": True,
                        "metadata": {
                            "score_type": s.score_type,
                            "score_value": s.value,
                            "missing_evidence": missing,
                        },
                    }
                )
                if missing:
                    claims.append(
                        {
                            "startup_id": startup_id,
                            "analysis_run_id": run_id,
                            "claim_text": (f"Missing evidence for {s.score_type}: {', '.join(missing)}"),
                            "claim_type": ClaimType.uncertainty_claim.value,
                            "support_level": SupportLevel.unsupported.value,
                            "confidence": "low",
                            "evidence_refs": [],
                            "used_in_score": True,
                            "used_in_gap": False,
                            "used_in_mapping": False,
                            "used_in_brief": True,
                            "metadata": {"missing_evidence": missing, "score_type": s.score_type},
                        }
                    )

        for gap in analysis_run.gaps:
            gap_refs = _normalize_evidence_refs(list(gap.evidence_refs_json), refs_by_id)
            if not gap.detected and not gap_refs:
                continue
            support = _calculate_support_level(gap_refs, gap.confidence)
            claims.append(
                {
                    "startup_id": startup_id,
                    "analysis_run_id": run_id,
                    "claim_text": (f"Gap: {gap.gap_type} (detected={gap.detected}, confidence={gap.confidence})"),
                    "claim_type": ClaimType.gap_claim.value,
                    "support_level": support,
                    "confidence": gap.confidence,
                    "evidence_refs": gap_refs,
                    "used_in_score": False,
                    "used_in_gap": True,
                    "used_in_mapping": True,
                    "used_in_brief": True,
                    "metadata": {
                        "gap_type": gap.gap_type,
                        "detected": gap.detected,
                        "evidence_tag": gap.evidence_tag,
                    },
                }
            )

        for mapping in analysis_run.mappings:
            mapping_refs = _normalize_evidence_refs(
                list(mapping.details_json.get("evidence_used", []))
                + list(mapping.details_json.get("rag_support_refs", [])),
                refs_by_id,
            )
            support = _calculate_support_level(mapping_refs, "medium")
            claims.append(
                {
                    "startup_id": startup_id,
                    "analysis_run_id": run_id,
                    "claim_text": (f"NVIDIA {mapping.technology_name} addresses {mapping.addresses_gap}"),
                    "claim_type": ClaimType.nvidia_fit_claim.value,
                    "support_level": support,
                    "confidence": "medium",
                    "evidence_refs": mapping_refs,
                    "used_in_score": False,
                    "used_in_gap": False,
                    "used_in_mapping": True,
                    "used_in_brief": True,
                    "metadata": {
                        "technology_name": mapping.technology_name,
                        "addresses_gap": mapping.addresses_gap,
                    },
                }
            )

        brief = analysis_run.briefs[0] if analysis_run.briefs else None
        if brief:
            used_claims = set()
            evidence_used = brief.brief_json.get("evidence_used", [])
            for item in evidence_used:
                if isinstance(item, dict):
                    claim_text = item.get("claim", "")
                    if claim_text:
                        used_claims.add(claim_text)
            for claim in claims:
                if claim["claim_text"] in used_claims:
                    claim["used_in_brief"] = True

        return claims

    def persist_claims_for_run(
        self,
        analysis_run: AnalysisRun,
    ) -> list[ClaimRecord]:
        self.repository.delete_claims_for_run(analysis_run.id)
        claim_dicts = self.build_claims_from_existing_records(analysis_run)
        records = self.repository.create_claims_bulk(claim_dicts)
        return records

    def get_claims_for_analysis_run(
        self,
        analysis_run_id: str,
        *,
        claim_type: str | None = None,
        support_level: str | None = None,
        review_status: str | None = None,
    ) -> list[ClaimRecord]:
        return self.repository.list_claims_for_analysis_run(
            analysis_run_id,
            claim_type=claim_type,
            support_level=support_level,
            review_status=review_status,
        )

    def get_evidence_coverage_for_analysis_run(
        self,
        analysis_run_id: str,
    ) -> dict[str, Any]:
        return self.repository.get_evidence_coverage_summary(analysis_run_id)

    def update_claim_review(
        self,
        claim_id: str,
        *,
        review_status: str,
        reviewer_notes: str = "",
    ) -> ClaimRecord | None:
        return self.repository.update_claim_review_status(
            claim_id,
            review_status=review_status,
            reviewer_notes=reviewer_notes,
        )

    def detect_unsupported_claims(
        self,
        analysis_run_id: str,
    ) -> list[dict[str, Any]]:
        coverage = self.repository.get_evidence_coverage_summary(analysis_run_id)
        issues: list[dict[str, Any]] = []

        unsupported_critical = self.repository.list_unsupported_critical_claims(analysis_run_id)
        if unsupported_critical:
            issues.append(
                {
                    "code": "UNSUPPORTED_CRITICAL_CLAIM",
                    "severity": "error",
                    "detail": (f"{len(unsupported_critical)} critical claim(s) without evidence support."),
                    "claim_ids": [c.id for c in unsupported_critical],
                }
            )

        if coverage["evidence_coverage"] < 0.5 and coverage["total_claims"] > 0:
            issues.append(
                {
                    "code": "LOW_EVIDENCE_COVERAGE",
                    "severity": "warning",
                    "detail": (
                        f"Evidence coverage is {coverage['evidence_coverage']:.0%} "
                        f"({coverage['supported_claims']}/"
                        f"{coverage['total_claims']} claims supported)."
                    ),
                    "claim_ids": [],
                }
            )

        return issues
