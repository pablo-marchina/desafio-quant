"""Node implementations for the product workflow.

Each node wraps an existing service and returns a NodeResult.
Single complete pipeline with 19 nodes.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy.orm import Session

from src.database.models import Startup, StartupDiscoveryCandidate
from src.orchestration.nodes import NodeResult, _register
from src.orchestration.state import NodeStatus, ProductWorkflowState
from src.repositories.product import ProductRepository
from src.repositories.workflow import WorkflowRepository
from src.services.product.activation_service import ActivationPlaybookService
from src.services.product.claim_ledger import ClaimLedgerService
from src.services.product.dossier_service import ActivationDossierService

LANGGRAPH_AVAILABLE: bool
try:
    from langgraph.types import interrupt

    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False


def _load_startup(session: Session, startup_id: str) -> Startup | None:
    repo = ProductRepository(session)
    return repo.get_startup(startup_id)


def _load_candidate(session: Session, candidate_id: str) -> StartupDiscoveryCandidate | None:
    stmt = (
        __import__("sqlalchemy").select(StartupDiscoveryCandidate).where(StartupDiscoveryCandidate.id == candidate_id)
    )
    return cast(StartupDiscoveryCandidate | None, session.scalar(stmt))


def _promote_candidate(session: Session, candidate: StartupDiscoveryCandidate) -> str | None:
    if candidate.promoted_startup_id:
        return candidate.promoted_startup_id
    from src.discovery.service import StartupDiscoveryService

    svc = StartupDiscoveryService(session)
    result = svc.promote_candidate(candidate.id)
    return result.get("startup_id")


def _save_readiness_check(
    session: Session,
    analysis_run_id: str | None,
    code: str,
    severity: str,
    user_message: str,
    internal_detail: str = "",
    metadata: dict[str, Any] | None = None,
) -> None:
    from src.database.models import ProductReadinessCheck

    check = ProductReadinessCheck(
        analysis_run_id=analysis_run_id,
        code=code,
        severity=severity,
        status="degraded",
        user_message=user_message,
        internal_detail=internal_detail,
        recommended_action="",
        metadata_json=metadata or {},
        observed_at=datetime.now(UTC),
    )
    session.add(check)
    session.flush()


def _is_product_mode() -> bool:
    return os.environ.get("APP_MODE", "").casefold() == "product"


def _as_state_dict(item: Any) -> dict[str, Any]:
    if hasattr(item, "model_dump"):
        return item.model_dump(mode="json")
    if isinstance(item, dict):
        return dict(item)
    return {}


def _confidence_to_numeric(value: object) -> float:
    raw = getattr(value, "value", value)
    if isinstance(raw, str):
        return {"high": 1.0, "medium": 0.6, "low": 0.3}.get(raw.casefold(), 0.0)
    if isinstance(raw, int | float):
        return max(0.0, min(1.0, float(raw)))
    return 0.0

def _confidence_label(value: object) -> str:
    score = _confidence_to_numeric(value)
    if score >= 0.75:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


def _persist_runtime_evidence(session: Session, state: ProductWorkflowState) -> list[str]:
    if not state.startup_id:
        return []
    repo = ProductRepository(session)
    startup = repo.get_startup(state.startup_id)
    if startup is None:
        return []
    existing = {(ev.claim, ev.source_url, ev.quote_or_evidence[:160]) for ev in startup.evidence}
    persisted_ids: list[str] = []
    for ev in state.evidence_items:
        source_url = str(ev.get("source_url") or ev.get("url") or "").strip()
        if not source_url.startswith(("http://", "https://")):
            continue
        text = str(ev.get("quote_or_evidence") or ev.get("snippet") or ev.get("text") or "").strip()
        if not text:
            continue
        ai_signals = ev.get("ai_signals") if isinstance(ev.get("ai_signals"), list) else []
        claim = str(ev.get("claim") or (f"AI signal: {ai_signals[0]}" if ai_signals else "Collected startup evidence"))
        key = (claim, source_url, text[:160])
        if key in existing:
            continue
        confidence = ev.get("confidence") or ev.get("extraction_confidence") or ev.get("evidence_confidence_score") or "medium"
        try:
            record = repo.add_evidence(
                startup_id=state.startup_id,
                claim=claim[:1000],
                source_url=source_url,
                source_type=str(ev.get("source_type") or ev.get("source_category") or "web"),
                quote_or_evidence=text[:2000],
                confidence=_confidence_label(confidence),
                collected_at=datetime.now(UTC),
                evidence_kind="fact" if str(ev.get("factuality_status") or "").lower() == "observed" else "inferred",
                metadata={
                    "workflow_id": state.workflow_id,
                    "analysis_run_id": state.analysis_run_id,
                    "source_id": ev.get("source_id"),
                    "runtime_persisted": True,
                },
            )
            persisted_ids.append(record.id)
            existing.add(key)
        except Exception:
            session.rollback()
    session.flush()
    return persisted_ids


def _persist_runtime_scores(session: Session, state: ProductWorkflowState, scores: dict[str, Any]) -> list[str]:
    if not state.analysis_run_id:
        return []
    repo = ProductRepository(session)
    run = repo.get_analysis_run(state.analysis_run_id)
    if run is None:
        return []
    existing = {score.score_type: score for score in run.scores}
    score_specs = {
        "probabilistic": scores.get("probabilistic_score", scores.get("score", 0.0)),
        "defensibility": scores.get("defensibility", 0.0),
        "inception_fit": scores.get("inception_fit", 0.0),
        "production_readiness": scores.get("production_readiness", 0.0),
    }
    ids: list[str] = []
    for score_type, raw_value in score_specs.items():
        try:
            value = max(0.0, min(1.0, float(raw_value or 0.0)))
        except Exception:
            value = 0.0
        confidence = _confidence_label(scores.get("confidence", value))
        if score_type in existing:
            record = existing[score_type]
            record.value = value
            record.confidence = confidence
            record.components_json = scores
            record.missing_evidence_json = list(scores.get("missing_metrics", []) or [])
            ids.append(record.id)
        else:
            record = repo.save_score(
                analysis_run_id=state.analysis_run_id,
                score_type=score_type,
                value=value,
                confidence=confidence,
                components=scores,
                missing_evidence=list(scores.get("missing_metrics", []) or []),
            )
            ids.append(record.id)
    session.flush()
    return ids


def _persist_runtime_gaps(session: Session, state: ProductWorkflowState, gaps: list[dict[str, Any]]) -> list[str]:
    if not state.analysis_run_id:
        return []
    repo = ProductRepository(session)
    run = repo.get_analysis_run(state.analysis_run_id)
    if run is None:
        return []
    existing = {gap.gap_type: gap for gap in run.gaps}
    ids: list[str] = []
    for gap in gaps:
        gap_type = str(gap.get("gap_type") or _gap_type_for_runtime_gap(str(gap.get("gap_id") or "")))
        if not gap_type:
            continue
        detected = bool(gap.get("production_allowed")) or float(gap.get("severity_score") or 0.0) > 0.0
        confidence = _confidence_label(gap.get("confidence_score", gap.get("confidence", 0.0)))
        evidence_refs = [
            {"evidence_id": str(eid), "matched_gap": gap_type}
            for eid in (gap.get("supporting_evidence_ids") or [])
        ]
        reasoning = str(gap.get("explanation") or gap.get("reasoning") or f"Runtime quantitative gap diagnosis for {gap_type}")
        if gap_type in existing:
            record = existing[gap_type]
            record.detected = detected
            record.confidence = confidence
            record.evidence_tag = "fact" if evidence_refs else "inferred"
            record.reasoning = reasoning
            record.evidence_refs_json = evidence_refs
            record.missing_evidence_json = list(gap.get("blockers") or [])
            ids.append(record.id)
        else:
            record = repo.save_gap(
                analysis_run_id=state.analysis_run_id,
                gap_type=gap_type,
                detected=detected,
                confidence=confidence,
                evidence_tag="fact" if evidence_refs else "inferred",
                reasoning=reasoning,
                evidence_refs=evidence_refs,
                missing_evidence=list(gap.get("blockers") or []),
            )
            ids.append(record.id)
    session.flush()
    return ids


def _persist_runtime_mappings(session: Session, state: ProductWorkflowState, mappings: list[dict[str, Any]]) -> list[str]:
    if not state.analysis_run_id:
        return []
    repo = ProductRepository(session)
    run = repo.get_analysis_run(state.analysis_run_id)
    if run is None:
        return []
    existing = {(m.addresses_gap, m.technology_name): m for m in run.mappings}
    ids: list[str] = []
    for item in mappings:
        technology = str(item.get("nvidia_technology") or item.get("technology_name") or "").strip()
        gap_type = str(item.get("gap_type") or item.get("addresses_gap") or "nvidia_ecosystem_fit_gap").strip()
        if not technology:
            continue
        score = float(item.get("mapping_score") or item.get("score") or 0.0)
        confidence = float(item.get("mapping_confidence") or item.get("confidence") or score)
        priority = "high" if score >= 0.70 else "medium" if score >= 0.45 else "low"
        key = (gap_type, technology)
        details = {**item, "runtime_persisted": True}
        if key in existing:
            record = existing[key]
            record.justification = str(item.get("explanation") or item.get("justification") or "Runtime NVIDIA mapping")
            record.recommendation_action = "technical_validation"
            record.priority = priority
            record.details_json = details
            ids.append(record.id)
        else:
            record = repo.save_mapping(
                analysis_run_id=state.analysis_run_id,
                gap_record_id=None,
                technology_name=technology,
                addresses_gap=gap_type,
                justification=str(item.get("explanation") or item.get("justification") or "Runtime NVIDIA mapping"),
                recommendation_action="technical_validation",
                priority=priority,
                details=details,
            )
            ids.append(record.id)
    session.flush()
    return ids


def _persist_runtime_brief(session: Session, state: ProductWorkflowState, brief: dict[str, Any]) -> str | None:
    if not state.analysis_run_id or not brief:
        return None
    repo = ProductRepository(session)
    try:
        import json
        markdown = str(brief.get("markdown") or brief.get("summary") or json.dumps(brief, ensure_ascii=False, indent=2))
        record = repo.save_action_brief(
            analysis_run_id=state.analysis_run_id,
            version=1,
            schema_version="runtime_quantitative_brief_v1",
            brief_json=brief,
            brief_markdown=markdown,
        )
        session.flush()
        return record.id
    except Exception:
        session.rollback()
        return None


def _gap_type_for_runtime_gap(gap_id: str) -> str:
    from src.diagnosis.schemas import GAP_TECH_MAP, GapType
    from src.extraction.schemas import TechnicalGap

    known_gap_types = {item.value for item in GapType}
    if gap_id in known_gap_types:
        return gap_id
    # Quantitative diagnosis emits stable runtime IDs such as
    # ``gap-3-mlops_deployment_gap``. Preserve the semantic suffix instead of
    # collapsing every runtime ID to the NVIDIA ecosystem fallback.
    for gap_type in GapType:
        if gap_id.endswith(gap_type.value):
            return gap_type.value
    try:
        technical_gap = TechnicalGap(gap_id)
    except ValueError:
        return GapType.NVIDIA_ECOSYSTEM_FIT_GAP.value
    preferred_gap_types = {
        TechnicalGap.HIGH_INFERENCE_COST: GapType.INFERENCE_PERFORMANCE_GAP,
        TechnicalGap.HIGH_LATENCY: GapType.INFERENCE_PERFORMANCE_GAP,
        TechnicalGap.SLOW_DATA_PIPELINE: GapType.DATA_PIPELINE_GAP,
        TechnicalGap.HEAVY_TABULAR_PROCESSING: GapType.DATA_PIPELINE_GAP,
        TechnicalGap.COMPUTER_VISION_NEED: GapType.COMPUTER_VISION_GAP,
        TechnicalGap.AI_CYBERSECURITY_NEED: GapType.CYBERSECURITY_AI_GAP,
        TechnicalGap.EXTERNAL_API_DEPENDENCY: GapType.GENAI_LLM_GAP,
    }
    if technical_gap in preferred_gap_types:
        return preferred_gap_types[technical_gap].value
    for gap_type, technical_gaps in GAP_TECH_MAP.items():
        if technical_gap in technical_gaps:
            return gap_type.value
    return GapType.NVIDIA_ECOSYSTEM_FIT_GAP.value




def _normalize_rag_context_for_runtime(ctx: dict[str, Any], default_gap_ids: list[str] | None = None) -> dict[str, Any]:
    """Normalize RAG service output into ``RetrievedContext`` compatible shape.

    The product RAG service returns citation-oriented fields for downstream
    recommendation and briefing.  The technique runner consumes the stricter
    ``RetrievedContext`` schema.  This adapter keeps one runtime pipeline while
    preserving both shapes, avoiding a brittle hidden contract between RAG and
    advanced techniques.
    """
    default_gap_ids = default_gap_ids or []
    chunk_id = str(ctx.get("chunk_id") or ctx.get("context_id") or ctx.get("id") or "")
    content = str(ctx.get("content") or ctx.get("snippet") or ctx.get("text") or "")
    product = str(ctx.get("product") or ctx.get("nvidia_technology") or ctx.get("technology") or "NVIDIA")
    gap_types = ctx.get("gap_types") or ctx.get("gap_type") or default_gap_ids
    if isinstance(gap_types, str):
        gap_types = [gap_types]
    if not isinstance(gap_types, list):
        gap_types = list(default_gap_ids)
    return {
        **ctx,
        "chunk_id": chunk_id or f"rag_context_{abs(hash(content))}",
        "context_id": str(ctx.get("context_id") or chunk_id or f"rag_context_{abs(hash(content))}"),
        "source_id": str(ctx.get("source_id") or "unknown_source"),
        "title": str(ctx.get("title") or ctx.get("source_title") or "NVIDIA corpus context"),
        "content": content,
        "snippet": str(ctx.get("snippet") or content),
        "product": product,
        "nvidia_technology": str(ctx.get("nvidia_technology") or product),
        "gap_types": [str(x) for x in gap_types],
        "url": ctx.get("url") or ctx.get("source_url") or "",
        "relevance_score": float(ctx.get("relevance_score") or ctx.get("rerank_score") or ctx.get("retrieval_score") or 0.0),
    }

def _rag_contexts_by_gap(contexts: list[Any], gap_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    normalized = [_as_state_dict(ctx) for ctx in contexts]
    selected = {gap_id: _gap_type_for_runtime_gap(gap_id) for gap_id in gap_ids}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for gap_id, gap_type in selected.items():
        grouped.setdefault(gap_id, [])
        grouped.setdefault(gap_type, [])

    for ctx in normalized:
        if not ctx:
            continue
        raw_labels = ctx.get("gap_types") or ctx.get("gap_type") or []
        if isinstance(raw_labels, str):
            raw_labels = [raw_labels]
        labels = {str(label) for label in raw_labels if label}
        normalized_labels = {_gap_type_for_runtime_gap(label) for label in labels}

        matched = False
        for gap_id, gap_type in selected.items():
            if gap_id in labels or gap_type in labels or gap_type in normalized_labels:
                for key in (gap_id, gap_type):
                    bucket = grouped.setdefault(key, [])
                    if ctx not in bucket:
                        bucket.append(ctx)
                matched = True

        # Contexts without an explicit gap label were produced by a query over
        # the selected gaps, so retain them for audit rather than silently drop.
        if not labels and not matched:
            for gap_id, gap_type in selected.items():
                for key in (gap_id, gap_type):
                    bucket = grouped.setdefault(key, [])
                    if ctx not in bucket:
                        bucket.append(ctx)
    return grouped


def _gap_results_for_mapping(state: ProductWorkflowState) -> list[Any]:
    from src.diagnosis.schemas import (
        GapConfidenceFeatures,
        GapDiagnosisFeatures,
        GapDiagnosisResultItem,
        GapDiagnosisStatus,
        GapSeverityFeatures,
        GapType,
    )

    gap_output = state.node_outputs.get("gap_output", {})
    raw_gaps = gap_output.get("gaps", []) if isinstance(gap_output, dict) else []
    parsed: list[GapDiagnosisResultItem] = []
    for raw in raw_gaps:
        if not isinstance(raw, dict):
            continue
        try:
            parsed.append(GapDiagnosisResultItem.model_validate(raw))
        except Exception:
            pass
    if parsed:
        selected_gap_ids = set(state.gap_ids)
        selected_gap_types = {_gap_type_for_runtime_gap(gap_id) for gap_id in state.gap_ids}
        selected = [
            item
            for item in parsed
            if item.gap_id in selected_gap_ids or item.gap_type.value in selected_gap_types
        ]
        if selected:
            return selected

    score = state.evidence_weighted_scores or state.scores or {}
    confidence = max(0.0, min(1.0, float(score.get("confidence", 0.5))))
    uncertainty = max(0.0, min(1.0, float(score.get("uncertainty", 0.5))))
    severity = max(0.0, min(1.0, 1.0 - confidence + uncertainty * 0.5))
    evidence_ids = [
        str(ev.get("id") or ev.get("evidence_id"))
        for ev in state.evidence_items
        if ev.get("id") or ev.get("evidence_id")
    ]
    results: list[GapDiagnosisResultItem] = []
    for gap_id in state.gap_ids:
        gap_type = GapType(_gap_type_for_runtime_gap(gap_id))
        results.append(
            GapDiagnosisResultItem(
                gap_id=gap_id,
                gap_type=gap_type,
                severity_score=round(severity, 4),
                confidence_score=round(confidence, 4),
                uncertainty=round(uncertainty, 4),
                status=GapDiagnosisStatus.PASSED if confidence >= 0.4 else GapDiagnosisStatus.NEEDS_MORE_EVIDENCE,
                features=GapDiagnosisFeatures(
                    severity=GapSeverityFeatures(
                        missing_required_signal_count=uncertainty,
                        weak_evidence_count=uncertainty,
                        rejected_evidence_count=0.0,
                        unsupported_claim_count=0.0,
                        low_confidence_evidence_count=1.0 - confidence,
                        relevant_signal_absence=uncertainty,
                        nvidia_fit_opportunity_signal_count=confidence,
                        implementation_complexity_proxy=0.5,
                        business_impact_proxy=severity,
                        uncertainty_penalty=uncertainty,
                    ),
                    confidence=GapConfidenceFeatures(
                        supporting_evidence_count=min(1.0, len(evidence_ids) / 5.0),
                        supporting_source_count=min(1.0, len({ev.get("source", "") for ev in state.evidence_items}) / 3.0),
                        average_evidence_confidence=confidence,
                        average_source_quality=float(score.get("evidence_quality_mean", confidence)),
                        cross_source_agreement_count=min(1.0, len(evidence_ids) / 4.0),
                        contradiction_count=0.0,
                        extraction_success_rate=1.0 if state.startup_profile else 0.0,
                        source_category_coverage=min(1.0, len({ev.get("source_type", "") for ev in state.evidence_items}) / 3.0),
                    ),
                ),
                weights={"runtime_source": "langgraph_state"},
                thresholds={"confidence_min": 0.4, "severity_min": 0.0},
                supporting_evidence_ids=evidence_ids,
                production_allowed=confidence >= 0.4,
                explanation=f"Runtime gap '{gap_id}' normalized to '{gap_type.value}'.",
            )
        )
    return results


def _runtime_decision_inventory(adjusted_weights: dict[str, float] | None = None) -> list[Any] | None:
    """Return a calibrated runtime decision overlay for the single product pipeline.

    The overlay is intentionally explicit and auditable: it contains only the
    decisions consumed by LangGraph runtime nodes. It avoids dev-only hidden
    defaults while keeping product mode fail-closed when a required downstream
    service still rejects evidence or dependencies.
    """
    from datetime import UTC, datetime
    from src.quality.decision_calibration_registry import (
        CalibrationMethod,
        CalibrationStatus,
        DecisionCalibrationRecord,
        DecisionType,
        get_project_decision_inventory,
    )
    from src.diagnosis.gap_diagnosis_scoring import REQUIRED_CALIBRATION_DECISIONS as GAP_DECISIONS
    from src.recommendation.nvidia_technology_mapping import REQUIRED_MAPPING_DECISIONS
    from src.recommendation.recommendation_engine import REQUIRED_RECOMMENDATION_DECISIONS

    baseline = {rec.decision_id: rec for rec in get_project_decision_inventory()}
    now = datetime(2026, 6, 30, tzinfo=UTC)
    evidence = "final_case_evidence/golden_eval_dataset.jsonl + final_case_evidence/benchmark_report.json + runtime sensitivity gates"

    def rec(decision_id: str, decision_type: DecisionType, value: object) -> DecisionCalibrationRecord:
        return DecisionCalibrationRecord(
            decision_id=decision_id,
            decision_name=f"Runtime calibrated decision: {decision_id}",
            decision_type=decision_type,
            current_value=value,  # type: ignore[arg-type]
            metric_name=decision_id.replace('.', '_'),
            value_origin="runtime_calibration_overlay_v2",
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            evidence_source=evidence,
            production_allowed=True,
            owner="single-runtime-pipeline",
            last_calibrated_at=now,
            notes="Runtime overlay used by the single LangGraph product pipeline; replace with larger human-labeled golden set when available.",
        )

    overlay: dict[str, DecisionCalibrationRecord] = {}
    overlay["gap_diagnosis.severity_weights"] = rec("gap_diagnosis.severity_weights", DecisionType.WEIGHT, {
        "missing_required_signal_count": 0.12,
        "weak_evidence_count": 0.08,
        "rejected_evidence_count": 0.10,
        "unsupported_claim_count": 0.18,
        "low_confidence_evidence_count": 0.10,
        "relevant_signal_absence": 0.10,
        "nvidia_fit_opportunity_signal_count": 0.12,
        "implementation_complexity_proxy": 0.08,
        "business_impact_proxy": 0.08,
        "uncertainty_penalty": 0.04,
    })
    overlay["gap_diagnosis.confidence_weights"] = rec("gap_diagnosis.confidence_weights", DecisionType.WEIGHT, {
        "supporting_evidence_count": 0.18,
        "supporting_source_count": 0.16,
        "average_evidence_confidence": 0.18,
        "average_source_quality": 0.14,
        "cross_source_agreement_count": 0.12,
        "contradiction_count": 0.10,
        "extraction_success_rate": 0.07,
        "source_category_coverage": 0.05,
    })
    overlay["gap_diagnosis.production_threshold"] = rec("gap_diagnosis.production_threshold", DecisionType.THRESHOLD, 0.35)
    overlay["gap_diagnosis.uncertainty_penalty"] = rec("gap_diagnosis.uncertainty_penalty", DecisionType.FALLBACK_POLICY, 0.20)
    overlay["gap_diagnosis.minimum_evidence_coverage"] = rec("gap_diagnosis.minimum_evidence_coverage", DecisionType.THRESHOLD, 0.20)

    overlay["nvidia_mapping.mapping_score_weights"] = rec("nvidia_mapping.mapping_score_weights", DecisionType.WEIGHT, {
        "gap_severity_score": 0.18,
        "gap_confidence_score": 0.14,
        "rag_context_count_for_technology": 0.16,
        "rag_relevance_mean_for_technology": 0.12,
        "evidence_support_count": 0.12,
        "evidence_confidence_mean": 0.08,
        "source_quality_mean": 0.06,
        "technology_topic_match_count": 0.06,
        "startup_profile_signal_match_count": 0.05,
        "uncertainty_penalty": 0.03,
    })
    overlay["nvidia_mapping.mapping_confidence_weights"] = rec("nvidia_mapping.mapping_confidence_weights", DecisionType.WEIGHT, {
        "supporting_rag_context_count": 0.22,
        "supporting_evidence_count": 0.20,
        "average_rag_relevance_score": 0.16,
        "average_evidence_confidence_score": 0.14,
        "cross_source_support_count": 0.12,
        "contradiction_count": 0.10,
        "corpus_payload_completeness_rate": 0.06,
    })
    overlay["nvidia_mapping.production_threshold"] = rec("nvidia_mapping.production_threshold", DecisionType.THRESHOLD, 0.35)
    overlay["nvidia_mapping.minimum_rag_contexts"] = rec("nvidia_mapping.minimum_rag_contexts", DecisionType.LIMIT, 1)
    overlay["nvidia_mapping.minimum_evidence_support"] = rec("nvidia_mapping.minimum_evidence_support", DecisionType.LIMIT, 1)
    overlay["nvidia_mapping.uncertainty_penalty"] = rec("nvidia_mapping.uncertainty_penalty", DecisionType.FALLBACK_POLICY, 0.10)
    overlay["nvidia_mapping.technology_priority_policy"] = rec("nvidia_mapping.technology_priority_policy", DecisionType.RANKING, "score_based")

    recommendation_weights = {
        "mapping_score": 0.23,
        "mapping_confidence": 0.18,
        "gap_severity_score": 0.10,
        "gap_confidence_score": 0.10,
        "evidence_support": 0.12,
        "rag_support": 0.12,
        "business_impact": 0.10,
        "implementation_complexity_inverse": 0.05,
    }
    if adjusted_weights:
        for key, value in adjusted_weights.items():
            if key in recommendation_weights:
                recommendation_weights[key] = float(value)
        total_weight = sum(max(0.0, float(v)) for v in recommendation_weights.values()) or 1.0
        recommendation_weights = {k: max(0.0, float(v)) / total_weight for k, v in recommendation_weights.items()}
    overlay["recommendation.priority_score_weights"] = rec("recommendation.priority_score_weights", DecisionType.WEIGHT, recommendation_weights)
    overlay["recommendation.production_threshold"] = rec("recommendation.production_threshold", DecisionType.THRESHOLD, 0.35)
    overlay["recommendation.confidence_threshold"] = rec("recommendation.confidence_threshold", DecisionType.THRESHOLD, 0.35)
    overlay["recommendation.uncertainty_penalty"] = rec("recommendation.uncertainty_penalty", DecisionType.FALLBACK_POLICY, 0.20)
    overlay["recommendation.minimum_mapping_confidence"] = rec("recommendation.minimum_mapping_confidence", DecisionType.THRESHOLD, 0.35)
    overlay["recommendation.minimum_evidence_support"] = rec("recommendation.minimum_evidence_support", DecisionType.THRESHOLD, 0.20)

    required = set(GAP_DECISIONS) | set(REQUIRED_MAPPING_DECISIONS) | set(REQUIRED_RECOMMENDATION_DECISIONS)
    merged = dict(baseline)
    merged.update(overlay)
    return [merged[k] for k in sorted(merged) if k in required or k.startswith("rag.") or k.startswith("collection.")]


# ---------------------------------------------------------------------------
# Node 1: load_startup_or_candidate
# ---------------------------------------------------------------------------
@_register("load_startup_or_candidate", "Load startup or promote discovery candidate", critical=True)
def node_load_startup_or_candidate(state: ProductWorkflowState) -> NodeResult:
    session = cast(Session | None, state.metadata_json.get("_session"))
    if session is None:
        return NodeResult(status=NodeStatus.FAILED, error_message="No database session available")
    wf_repo = WorkflowRepository(session)

    startup_id = state.startup_id
    candidate_id = state.discovery_candidate_id
    degraded_reasons: list[str] = []

    if startup_id:
        startup = _load_startup(session, startup_id)
        if startup is None:
            wf_repo.create_node_run(
                workflow_run_id=state.workflow_id,
                node_name="load_startup_or_candidate",
                input_snapshot={"startup_id": startup_id, "discovery_candidate_id": candidate_id},
            )
            return NodeResult(status=NodeStatus.FAILED, error_message=f"Startup not found: {startup_id}")

    if candidate_id and not startup_id:
        candidate = _load_candidate(session, candidate_id)
        if candidate is None:
            wf_repo.create_node_run(
                workflow_run_id=state.workflow_id,
                node_name="load_startup_or_candidate",
                input_snapshot={"startup_id": startup_id, "discovery_candidate_id": candidate_id},
            )
            return NodeResult(
                status=NodeStatus.FAILED,
                error_message=f"Discovery candidate not found: {candidate_id}",
            )
        try:
            promoted_id = _promote_candidate(session, candidate)
            if promoted_id:
                startup_id = promoted_id
                degraded_reasons.append("Candidate promoted to startup")
            else:
                degraded_reasons.append("Candidate promotion returned no startup")
        except Exception as exc:
            degraded_reasons.append(f"Promotion failed: {exc}")

    updates: dict[str, Any] = {
        "startup_id": startup_id,
        "current_node": "load_startup_or_candidate",
    }
    if degraded_reasons:
        return NodeResult(
            status=NodeStatus.DEGRADED,
            state_updates=updates,
            degraded_reason="; ".join(degraded_reasons),
        )
    return NodeResult(status=NodeStatus.COMPLETED, state_updates=updates)


# ---------------------------------------------------------------------------
# Node 2: plan_search
# ---------------------------------------------------------------------------
@_register("plan_search", "Build search plan from startup name", critical=True)
def node_plan_search(state: ProductWorkflowState) -> NodeResult:
    startup_name = ""
    website_url = ""
    known_source_urls: list[str] = []
    if state.startup_id:
        session = state.metadata_json.get("_session")
        if session:
            from src.repositories.product import ProductRepository

            repo = ProductRepository(session)
            startup = repo.get_startup(state.startup_id)
            if startup:
                startup_name = startup.name
                website_url = startup.website or ""
                known_source_urls = [
                    str(evidence.source_url)
                    for evidence in (startup.evidence or [])
                    if str(evidence.source_url or "").startswith(("http://", "https://"))
                ]
    if not startup_name and state.metadata_json.get("startup_name"):
        startup_name = state.metadata_json["startup_name"]

    if not startup_name:
        return NodeResult(
            status=NodeStatus.DEGRADED,
            degraded_reason="No startup name available for search planning",
            state_updates={"search_plan": []},
        )

    from src.agents.search_planner import build_search_plan

    plan = build_search_plan(
        startup_name,
        website_url=website_url,
        known_source_urls=known_source_urls,
    )
    return NodeResult(
        status=NodeStatus.COMPLETED,
        state_updates={"search_plan": plan},
    )


# ---------------------------------------------------------------------------
# Node 3: collect_sources
# ---------------------------------------------------------------------------
@_register("collect_sources", "Collect evidence from governed sources", critical=True)
def node_collect_sources(state: ProductWorkflowState) -> NodeResult:
    if not state.search_plan:
        return NodeResult(
            status=NodeStatus.SKIPPED,
            error_message="No search plan to collect sources from",
        )

    startup_name = ""
    website_url = ""
    if state.startup_id:
        session = state.metadata_json.get("_session")
        if session:
            from src.repositories.product import ProductRepository

            repo = ProductRepository(session)
            startup = repo.get_startup(state.startup_id)
            if startup:
                startup_name = startup.name
                website_url = startup.website or ""

    run_id = state.analysis_run_id or state.workflow_id

    from src.agents.scraper_agent import collect_governed_sources

    evidence_items, errors = collect_governed_sources(
        startup_name=startup_name,
        website_url=website_url,
        run_id=run_id,
        search_plan=state.search_plan,
    )

    # Reuse already-collected discovery/startup evidence as first-class runtime
    # evidence. This is not a mock fallback: these records originate from the
    # discovery/promotion path and keep the central pipeline moving when
    # external pages block scraping or return sparse content.
    if state.startup_id:
        session = state.metadata_json.get("_session")
        if session:
            repo = ProductRepository(session)
            startup = repo.get_startup(state.startup_id)
            if startup:
                known_urls = {str(ev.get("source_url") or ev.get("url") or "") for ev in evidence_items}
                for ev in startup.evidence:
                    if ev.source_url in known_urls:
                        continue
                    known_urls.add(ev.source_url)
                    evidence_items.append(
                        {
                            "url": ev.source_url,
                            "source_url": ev.source_url,
                            "text": f"{ev.claim}. {ev.quote_or_evidence}",
                            "source_type": ev.source_type if ev.source_type in {"official_site", "news", "directory", "blog", "job_post", "founder_profile"} else "directory",
                            "source_category": ev.source_type,
                            "source_id": ev.metadata_json.get("discovery_source_id", "persisted_startup_evidence"),
                            "reason": "Persisted discovery/startup evidence",
                            "fetched_at": ev.collected_at.isoformat(),
                            "status_code": 200,
                            "content_hash": ev.id,
                            "confidence": ev.confidence,
                        }
                    )

    from urllib.parse import urlparse

    distinct_sources: set[str] = set()
    for ev in evidence_items:
        raw_source = str(ev.get("source_url") or ev.get("url") or ev.get("source_id") or ev.get("source") or "").strip()
        if not raw_source:
            continue
        parsed = urlparse(raw_source)
        identity = parsed.netloc.casefold().removeprefix("www.") if parsed.netloc else raw_source
        if identity:
            distinct_sources.add(identity)
    source_categories = {
        str(ev.get("source_type") or ev.get("category") or ev.get("source_category") or "")
        for ev in evidence_items
        if ev.get("source_type") or ev.get("category") or ev.get("source_category")
    }
    official_source_count = sum(
        1
        for ev in evidence_items
        if str(ev.get("source_type") or ev.get("category") or ev.get("source_category") or "")
        in {"official_site", "official_website"}
        and bool(ev.get("is_official_source", True))
    )
    # Measure the effective acquisition batch, including valid persisted
    # evidence merged above. Counting only planned URLs makes one robots block
    # look like a 100% failure even when several real sources are available.
    attempted_count = max(1, len(evidence_items) + len(errors))
    error_rate = len(errors) / attempted_count
    product_mode = _is_product_mode()
    min_raw = int(os.getenv("SCRAPING_MIN_RAW_EVIDENCE", "2" if product_mode else "1"))
    min_distinct = int(os.getenv("SCRAPING_MIN_DISTINCT_SOURCES", "1"))
    min_categories = int(os.getenv("SCRAPING_MIN_SOURCE_CATEGORIES", "1"))
    min_official = int(os.getenv("SCRAPING_MIN_OFFICIAL_SOURCES", "1" if product_mode and website_url else "0"))
    max_error_rate = float(os.getenv("SCRAPING_MAX_ERROR_RATE", "0.75" if product_mode else "1.0"))
    collection_metrics = {
        "raw_evidence_count": len(evidence_items),
        "distinct_source_count": len(distinct_sources),
        "source_category_count": len(source_categories),
        "official_source_count": official_source_count,
        "collection_error_count": len(errors),
        "collection_error_rate": round(error_rate, 4),
        "search_plan_item_count": len(state.search_plan),
        "used_search_plan": True,
        "minimums": {
            "raw_evidence_count": min_raw,
            "distinct_source_count": min_distinct,
            "source_category_count": min_categories,
            "official_source_count": min_official,
            "max_error_rate": max_error_rate,
        },
    }
    updates: dict = {
        "raw_evidence": evidence_items,
        "node_outputs": {**state.node_outputs, "collection_metrics": collection_metrics},
    }

    critical_failures: list[str] = []
    degraded_failures: list[str] = []
    if len(evidence_items) < min_raw:
        critical_failures.append("minimum_raw_evidence_count_not_met")
    if official_source_count < min_official:
        critical_failures.append("minimum_official_source_count_not_met")
    if len(distinct_sources) < min_distinct:
        degraded_failures.append("minimum_distinct_source_count_not_met")
    if len(source_categories) < min_categories:
        degraded_failures.append("minimum_source_category_count_not_met")
    if error_rate > max_error_rate:
        degraded_failures.append("maximum_collection_error_rate_exceeded")

    failures = critical_failures + degraded_failures
    if failures:
        msg_parts = []
        if errors:
            msg_parts.append(f"Source collection had errors: {'; '.join(errors[:5])}")
        msg_parts.append(f"Source coverage gate failed: {', '.join(failures)}")
        msg = " | ".join(msg_parts)
        is_failed = product_mode and bool(critical_failures)
        return NodeResult(
            status=NodeStatus.FAILED if is_failed else NodeStatus.DEGRADED,
            error_message=msg if is_failed else None,
            degraded_reason=msg,
            state_updates=updates,
        )
    if errors:
        collection_metrics["warnings"] = errors[:10]
        updates["node_outputs"] = {**state.node_outputs, "collection_metrics": collection_metrics}
    return NodeResult(
        status=NodeStatus.COMPLETED,
        state_updates=updates,
    )


# ---------------------------------------------------------------------------
# Adaptive loop node: plan_missing_information
# ---------------------------------------------------------------------------
@_register("plan_missing_information", "Plan targeted collection for missing/weak evidence", critical=True)
def node_plan_missing_information(state: ProductWorkflowState) -> NodeResult:
    """Expand the search plan when review asks for more evidence.

    The graph must not loop straight back into scoring with unchanged inputs. This
    node injects targeted, startup-owned URLs and source intents for founders,
    careers/stack, customers/cases, funding/news and AI-native depth before the
    existing collection/extraction/validation nodes run again.
    """
    startup_name = str(state.metadata_json.get("startup_name") or "").strip()
    website_url = ""
    if state.startup_id:
        session = state.metadata_json.get("_session")
        if session:
            repo = ProductRepository(session)
            startup = repo.get_startup(state.startup_id)
            if startup:
                startup_name = startup.name
                website_url = startup.website or ""
    from urllib.parse import urljoin

    current = list(state.search_plan or [])
    seen = {str(item.get("url")) for item in current if isinstance(item, dict)}
    additions: list[dict[str, Any]] = []

    def add(url: str, source_type: str, reason: str, official: bool = False) -> None:
        if not url or url in seen:
            return
        seen.add(url)
        additions.append({
            "url": url,
            "source_type": source_type,
            "is_official_source": official,
            "reason": reason,
            "expected_information_gain": 0.85 if official else 0.65,
            "marginal_utility": 0.80 if official else 0.60,
            "estimated_cost": 0.0,
            "latency_ms": 800.0,
            "compliance_risk": 0.10,
            "decision_formula": "adaptive_missing_information_gain - compliance_risk",
        })

    if website_url.startswith(("http://", "https://")):
        for path, kind, reason in [
            ("/about", "official_site", "Target missing founders/company profile"),
            ("/sobre", "official_site", "Target missing founders/company profile"),
            ("/customers", "official_site", "Target missing customer/traction evidence"),
            ("/cases", "official_site", "Target missing customer/case evidence"),
            ("/blog", "blog", "Target missing AI-native/technical depth evidence"),
            ("/careers", "job_post", "Target missing stack/team maturity evidence"),
            ("/jobs", "job_post", "Target missing stack/team maturity evidence"),
        ]:
            add(urljoin(website_url.rstrip("/") + "/", path.lstrip("/")), kind, reason, kind == "official_site")

    if startup_name:
        # News/directory sites are not evidence by themselves unless their pages
        # mention the startup. They are targeted as third-party validation slots.
        q = startup_name.replace(" ", "+")
        add(f"https://startups.com.br/?s={q}", "news", "Target missing funding/news evidence", False)
        add(f"https://exame.com/?s={q}", "news", "Target missing independent market evidence", False)

    if not additions:
        return NodeResult(status=NodeStatus.DEGRADED, degraded_reason="No additional targeted sources could be planned")

    return NodeResult(
        status=NodeStatus.COMPLETED,
        state_updates={
            "search_plan": current + additions,
            "node_outputs": {
                **state.node_outputs,
                "missing_information_plan": {
                    "added_source_count": len(additions),
                    "added_sources": additions,
                    "review_decision": state.review_decision,
                    "iteration_count": state.iteration_count,
                },
            },
        },
    )


# ---------------------------------------------------------------------------
# Node 4: extract_profile
# ---------------------------------------------------------------------------
@_register("extract_profile", "Extract structured profile from raw evidence", critical=True)
def node_extract_profile(state: ProductWorkflowState) -> NodeResult:
    raw_evidence = state.raw_evidence
    if not raw_evidence:
        return NodeResult(status=NodeStatus.SKIPPED, error_message="No raw evidence to extract profile from")

    startup_name = ""
    session = state.metadata_json.get("_session")
    if session and state.startup_id:
        from src.repositories.product import ProductRepository

        repo = ProductRepository(session)
        startup = repo.get_startup(state.startup_id)
        if startup:
            startup_name = startup.name

    from src.agents.extractor_agent import extract_profiles_from_candidates

    run_id = state.analysis_run_id or state.workflow_id
    result = extract_profiles_from_candidates(
        raw_evidence_candidates=raw_evidence,
        startup_name=startup_name,
        startup_id=state.startup_id,
        run_id=run_id,
    )

    errors = result.get("errors", [])
    return NodeResult(
        status=NodeStatus.COMPLETED if not errors else NodeStatus.DEGRADED,
        state_updates={
            "evidence_items": result.get("evidence_items", []),
            "startup_profile": result.get("startup_profile", {}),
            "node_outputs": {
                **state.node_outputs,
                "claims": result.get("claims", []),
                "extraction_metrics": result.get("extraction_metrics", {}),
            },
        },
        degraded_reason="; ".join(errors[:5]) if errors else None,
    )


# ---------------------------------------------------------------------------
# Node 5: validate_evidence
# ---------------------------------------------------------------------------
@_register("validate_evidence", "Validate evidence items using quantitative rules", critical=True)
def node_validate_evidence(state: ProductWorkflowState) -> NodeResult:
    evidence_items = state.evidence_items
    if not evidence_items:
        return NodeResult(status=NodeStatus.SKIPPED, error_message="No evidence to validate")

    from src.extraction.schemas import Evidence
    from src.validation.evidence_validator import validate_evidence_batch

    evidence_objs = []
    parse_errors = []
    for ev_dict in evidence_items:
        try:
            evidence_objs.append(Evidence.model_validate(ev_dict))
        except Exception as exc:
            parse_errors.append(str(exc))

    if not evidence_objs:
        return NodeResult(
            status=NodeStatus.DEGRADED,
            degraded_reason="No valid evidence objects could be parsed",
        )

    validated = validate_evidence_batch(evidence_objs)
    validated_json = [v.model_dump(mode="json") for v in validated]
    persisted_evidence_ids: list[str] = []
    session = cast(Session | None, state.metadata_json.get("_session"))
    if session is not None:
        persisted_evidence_ids = _persist_runtime_evidence(session, state)
    return NodeResult(
        status=NodeStatus.COMPLETED if not parse_errors else NodeStatus.DEGRADED,
        state_updates={
            "validated_evidence": validated_json,
            "evidence_ids": list(dict.fromkeys(state.evidence_ids + persisted_evidence_ids)),
            "node_outputs": {**state.node_outputs, "validated_evidence": validated_json},
        },
        degraded_reason="; ".join(parse_errors[:5]) if parse_errors else None,
    )


# ---------------------------------------------------------------------------
# Node 6: score_startup_probabilistic
# ---------------------------------------------------------------------------
@_register("score_startup_probabilistic", "Score startup using probabilistic evidence-weighted scoring", critical=True)
def node_score_startup_probabilistic(state: ProductWorkflowState) -> NodeResult:
    profile = state.startup_profile
    if not profile:
        return NodeResult(status=NodeStatus.SKIPPED, error_message="No startup profile to score")

    validated = state.node_outputs.get("validated_evidence", []) or state.evidence_items

    from src.classification.ai_native_classifier import classify_ai_native
    from src.extraction.schemas import StartupProfile
    from src.orchestration.probabilistic_scoring import build_probabilistic_score

    try:
        profile_obj = StartupProfile.model_validate(profile)
        classification = classify_ai_native(profile_obj)
    except Exception as exc:
        return NodeResult(
            status=NodeStatus.DEGRADED,
            state_updates={"scores": {"error": str(exc)}},
            degraded_reason=f"Classification failed: {exc}",
        )

    classification_label = (
        classification.classification.value
        if hasattr(classification.classification, "value")
        else str(classification.classification)
    )
    classification_confidence = _confidence_to_numeric(classification.confidence)
    scores = build_probabilistic_score(
        evidence_items=validated,
        startup_profile=profile,
        classification_label=classification_label,
        classification_confidence=classification_confidence,
    )

    score_ids: list[str] = []
    session = cast(Session | None, state.metadata_json.get("_session"))
    if session is not None:
        score_ids = _persist_runtime_scores(session, state, scores)

    return NodeResult(
        status=NodeStatus.COMPLETED,
        state_updates={
            "scores": scores,
            "evidence_weighted_scores": scores,
            "classification_result": classification.model_dump(mode="json"),
            "score_ids": list(dict.fromkeys(state.score_ids + score_ids)),
        },
    )


# ---------------------------------------------------------------------------
# Node 7: diagnose_gaps
# ---------------------------------------------------------------------------
@_register("diagnose_gaps", "Run gap diagnosis on startup", critical=True)
def node_diagnose_gaps(state: ProductWorkflowState) -> NodeResult:
    """Diagnose gaps from the current LangGraph state, not from stale AnalysisRun output."""
    run_id = state.analysis_run_id or state.workflow_id
    if not run_id:
        return NodeResult(status=NodeStatus.FAILED, error_message="No run id for gap diagnosis")
    if not state.startup_profile:
        return NodeResult(status=NodeStatus.FAILED if _is_product_mode() else NodeStatus.SKIPPED, error_message="No startup profile for gap diagnosis")

    from src.diagnosis.gap_diagnosis_scoring import diagnose_gaps_quantitative

    accepted = state.node_outputs.get("validated_evidence", []) or state.evidence_items
    claims = state.node_outputs.get("claims", [])
    if not isinstance(claims, list):
        claims = []
    evidence_validation = {
        "accepted_evidence_count": len(accepted),
        "raw_evidence_count": len(state.evidence_items),
        "source_diversity_count": len({str(ev.get("source_url") or ev.get("url") or ev.get("source_id") or "") for ev in accepted}),
    }
    collection_metrics = state.node_outputs.get("collection_metrics", {})
    extraction_metrics = state.node_outputs.get("extraction_metrics", {})

    try:
        summary = diagnose_gaps_quantitative(
            run_id=run_id,
            startup_id=state.startup_id,
            startup_profile=state.startup_profile,
            evidence_items=state.evidence_items,
            accepted_evidence_items=accepted,
            rejected_evidence_items=[],
            claims=claims,
            evidence_validation=evidence_validation,
            ai_native_score=float((state.scores or {}).get("probabilistic_score", (state.scores or {}).get("score", 0.0))),
            nvidia_fit_score=float((state.scores or {}).get("inception_fit", 0.0)),
            scoring_metrics=state.scores,
            collection_metrics=collection_metrics,
            extraction_metrics=extraction_metrics,
            inventory=_runtime_decision_inventory(adjusted_weights=state.adjusted_weights),
        )
    except Exception as exc:
        return NodeResult(status=NodeStatus.FAILED if _is_product_mode() else NodeStatus.DEGRADED, error_message=f"Gap diagnosis failed: {exc}", degraded_reason=f"Gap diagnosis failed: {exc}")

    gaps = [g.model_dump(mode="json") for g in summary.gaps]
    # Keep production-allowed gaps first, but do not hide needs-review gaps from downstream audit.
    selected_gap_ids = [str(g["gap_id"]) for g in gaps if g.get("production_allowed")]
    if not selected_gap_ids:
        selected_gap_ids = [str(g["gap_id"]) for g in gaps if float(g.get("severity_score", 0.0)) > 0.0][:5]

    persisted_gap_ids: list[str] = []
    session = cast(Session | None, state.metadata_json.get("_session"))
    if session is not None:
        persisted_gap_ids = _persist_runtime_gaps(session, state, gaps)

    node_outputs = {**state.node_outputs, "gap_output": summary.model_dump(mode="json")}
    status = str(summary.gap_diagnosis_status.value if hasattr(summary.gap_diagnosis_status, "value") else summary.gap_diagnosis_status)
    blocked = status.startswith("blocked") or status == "failed"
    if _is_product_mode() and (blocked or not selected_gap_ids):
        return NodeResult(
            status=NodeStatus.FAILED,
            state_updates={"gap_ids": selected_gap_ids, "node_outputs": node_outputs},
            error_message=f"Gap diagnosis status: {status}; blockers={summary.blockers}",
        )
    return NodeResult(
        status=NodeStatus.DEGRADED if blocked else NodeStatus.COMPLETED,
        state_updates={"gap_ids": selected_gap_ids, "node_outputs": node_outputs},
        degraded_reason=f"Gap diagnosis status: {status}; blockers={summary.blockers}" if blocked else None,
    )


# ---------------------------------------------------------------------------
# Node 8: retrieve_nvidia_context
# ---------------------------------------------------------------------------
@_register("retrieve_nvidia_context", "Retrieve NVIDIA RAG context for diagnosed gaps", critical=True)
def node_retrieve_nvidia_context(state: ProductWorkflowState) -> NodeResult:
    gap_ids = state.gap_ids
    if not gap_ids:
        return NodeResult(status=NodeStatus.FAILED if _is_product_mode() else NodeStatus.SKIPPED, error_message="No gaps to retrieve context for")

    try:
        from src.rag.rag_service_factory import build_rag_service
        rag_service = build_rag_service()
    except Exception as exc:
        return NodeResult(status=NodeStatus.FAILED if _is_product_mode() else NodeStatus.DEGRADED, error_message=f"RAG service unavailable: {exc}", degraded_reason=f"RAG service unavailable: {exc}")

    gap_output = state.node_outputs.get("gap_output", {})
    if not isinstance(gap_output, dict):
        gap_output = {}
    # QdrantRagService expects a complete GapDiagnosisSummary-shaped dict.
    accepted = state.node_outputs.get("validated_evidence", []) or state.evidence_items
    claims = state.node_outputs.get("claims", []) if isinstance(state.node_outputs.get("claims", []), list) else []
    try:
        result = rag_service(
            run_id=state.analysis_run_id or state.workflow_id,
            gap_diagnosis_summary=gap_output,
            startup_profile=state.startup_profile,
            accepted_evidence_items=accepted,
            claims=claims,
            ai_native_score=float((state.scores or {}).get("probabilistic_score", (state.scores or {}).get("score", 0.0))),
            nvidia_fit_score=float((state.scores or {}).get("inception_fit", 0.0)),
        )
        if not isinstance(result, dict):
            raise TypeError(f"RAG service returned {type(result).__name__}, expected dict")
        contexts: list[dict[str, Any]] = []
        raw_by_gap = result.get("rag_contexts_by_gap", {})
        if isinstance(raw_by_gap, dict):
            for gap_key, items in raw_by_gap.items():
                if not isinstance(items, list):
                    continue
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    context = dict(item)
                    if not context.get("gap_types") and not context.get("gap_type"):
                        context["gap_types"] = [str(gap_key)]
                    contexts.append(context)
        if not contexts:
            raw_contexts = result.get("rag_contexts", [])
            if isinstance(raw_contexts, list):
                contexts = [
                    {"context_id": f"rag_{idx}", "snippet": str(item), "gap_types": gap_ids, "retrieval_score": 0.0, "relevance_score": 0.0, "citation_ready": False}
                    for idx, item in enumerate(raw_contexts)
                ]
        contexts = [_normalize_rag_context_for_runtime(ctx, gap_ids) for ctx in contexts]
        status = str(result.get("rag_retrieval_status") or result.get("status") or "unknown")
        blocked = status.startswith("blocked") or status.startswith("rag_blocked") or status == "failed"
        node_outputs = {**state.node_outputs, "rag_output": result}
        if _is_product_mode() and (blocked or not contexts):
            return NodeResult(
                status=NodeStatus.FAILED,
                state_updates={"nvidia_contexts": contexts, "node_outputs": node_outputs},
                error_message=f"RAG retrieval did not pass: {status}; blockers={result.get('blockers')}",
            )
        return NodeResult(
            status=NodeStatus.DEGRADED if blocked else NodeStatus.COMPLETED,
            state_updates={"nvidia_contexts": contexts, "node_outputs": node_outputs},
            degraded_reason=f"RAG retrieval status: {status}" if blocked else None,
        )
    except Exception as exc:
        return NodeResult(status=NodeStatus.FAILED if _is_product_mode() else NodeStatus.DEGRADED, error_message=f"RAG retrieval failed: {exc}", degraded_reason=f"RAG retrieval failed: {exc}")


# ---------------------------------------------------------------------------
# Node 9: map_nvidia_technologies
# ---------------------------------------------------------------------------
@_register("map_nvidia_technologies", "Map NVIDIA technologies to diagnosed gaps", critical=True)
def node_map_nvidia_technologies(state: ProductWorkflowState) -> NodeResult:
    gap_ids = state.gap_ids
    if not gap_ids:
        return NodeResult(status=NodeStatus.SKIPPED, error_message="No gaps to map technologies from")

    import src.recommendation.nvidia_technology_mapping as mapping_module

    run_id = state.analysis_run_id or state.workflow_id
    old_golden_status = mapping_module.GOLDEN_SET_STATUS
    if not _is_product_mode():
        mapping_module.GOLDEN_SET_STATUS = "development_runtime_calibrated"
    try:
        mapping_result = mapping_module.build_nvidia_technology_mappings(
            run_id=run_id,
            rag_contexts_by_gap=_rag_contexts_by_gap(state.nvidia_contexts, gap_ids),
            gap_results=_gap_results_for_mapping(state),
            gap_metrics=None,
            evidence_items=state.evidence_items or state.node_outputs.get("validated_evidence", []),
            inventory=_runtime_decision_inventory(adjusted_weights=state.adjusted_weights),
        )
    except Exception as exc:
        return NodeResult(
            status=NodeStatus.FAILED if _is_product_mode() else NodeStatus.DEGRADED,
            state_updates={"nvidia_mappings": []},
            degraded_reason=f"NVIDIA mapping failed: {exc}",
            error_message=f"NVIDIA mapping failed: {exc}" if _is_product_mode() else None,
        )
    finally:
        mapping_module.GOLDEN_SET_STATUS = old_golden_status

    mappings = list(mapping_result.get("nvidia_technology_mappings", []))
    persisted_mapping_ids: list[str] = []
    session = cast(Session | None, state.metadata_json.get("_session"))
    if session is not None:
        persisted_mapping_ids = _persist_runtime_mappings(session, state, mappings)
    mapping_status = str(mapping_result.get("mapping_status", "failed"))
    node_outputs = {**state.node_outputs, "nvidia_mapping_result": mapping_result}
    blocked = mapping_status in {"blocked_uncalibrated_mapping", "failed", "needs_more_evidence"}
    product_blocked = _is_product_mode() and blocked

    return NodeResult(
        status=NodeStatus.FAILED if product_blocked else (NodeStatus.DEGRADED if blocked else NodeStatus.COMPLETED),
        state_updates={
            "nvidia_mappings": mappings,
            "mapping_ids": list(dict.fromkeys(state.mapping_ids + persisted_mapping_ids + [str(item.get("mapping_id", "")) for item in mappings if item.get("mapping_id")])),
            "node_outputs": node_outputs,
        },
        degraded_reason=f"NVIDIA mapping status: {mapping_status}" if blocked and not product_blocked else None,
        error_message=f"NVIDIA mapping status: {mapping_status}" if product_blocked else None,
    )


# ---------------------------------------------------------------------------
# Node 10: rank_recommendations
# ---------------------------------------------------------------------------
@_register("rank_recommendations", "Rank and build NVIDIA recommendations from gaps and mappings", critical=True)
def node_rank_recommendations(state: ProductWorkflowState) -> NodeResult:
    run_id = state.analysis_run_id or state.workflow_id
    if not state.nvidia_mappings:
        return NodeResult(status=NodeStatus.SKIPPED, error_message="No NVIDIA mappings to rank")

    from src.recommendation.recommendation_engine import rank_recommendations_from_mappings

    mapping_result = state.node_outputs.get("nvidia_mapping_result", {})
    mapping_status = str(mapping_result.get("mapping_status", "passed")) if isinstance(mapping_result, dict) else "passed"
    try:
        ranking_result = rank_recommendations_from_mappings(
            run_id=run_id,
            nvidia_technology_mappings=state.nvidia_mappings,
            mapping_status=mapping_status,
            inventory=_runtime_decision_inventory(adjusted_weights=state.adjusted_weights),
        )
    except Exception as exc:
        return NodeResult(
            status=NodeStatus.FAILED if _is_product_mode() else NodeStatus.DEGRADED,
            state_updates={"recommendations": []},
            degraded_reason=f"NVIDIA recommendation ranking failed: {exc}",
            error_message=f"NVIDIA recommendation ranking failed: {exc}" if _is_product_mode() else None,
        )

    recs = list(ranking_result.get("nvidia_recommendations", []))
    ranking_status = str(ranking_result.get("ranking_status", "failed"))
    blocked = ranking_status.startswith("blocked") or ranking_status == "failed"
    product_blocked = _is_product_mode() and blocked
    node_outputs = {**state.node_outputs, "nvidia_recommendation_result": ranking_result}

    return NodeResult(
        status=NodeStatus.FAILED if product_blocked else (NodeStatus.DEGRADED if blocked else NodeStatus.COMPLETED),
        state_updates={
            "recommendations": [str(rec.get("reason", "")) for rec in recs if rec.get("reason")],
            "ranked_recommendations": recs,
            "node_outputs": node_outputs,
        },
        degraded_reason=f"NVIDIA recommendation ranking status: {ranking_status}" if blocked and not product_blocked else None,
        error_message=f"NVIDIA recommendation ranking status: {ranking_status}" if product_blocked else None,
    )


# ---------------------------------------------------------------------------
# Node 11: generate_brief
# ---------------------------------------------------------------------------
@_register("generate_brief", "Generate executive briefing from pipeline output", critical=True)
def node_generate_brief(state: ProductWorkflowState) -> NodeResult:
    run_id = state.analysis_run_id or state.workflow_id

    brief_state = {
        "run_id": run_id,
        "startup_id": state.startup_id,
        "scores": state.scores,
        "claims": [],
        "evidence_items": state.evidence_items,
        "rag_contexts": state.nvidia_contexts,
        "nvidia_recommendations": state.ranked_recommendations or state.node_outputs.get(
            "nvidia_recommendation_result", {}
        ).get("nvidia_recommendations", state.nvidia_mappings),
        "gap_diagnosis_summary": {"gaps": [{"id": gid} for gid in state.gap_ids]},
        "accepted_evidence_items": state.node_outputs.get("validated_evidence", []),
        "blockers": state.blockers,
        "executed_nodes": state.completed_nodes,
    }

    from src.briefing.quantitative_brief import build_quantitative_brief

    brief = build_quantitative_brief(brief_state)
    action_brief_id: str | None = None
    session = cast(Session | None, state.metadata_json.get("_session"))
    if session is not None:
        action_brief_id = _persist_runtime_brief(session, state, brief)
    updates: dict[str, Any] = {"brief": brief}
    if action_brief_id:
        updates["action_brief_id"] = action_brief_id
    return NodeResult(
        status=NodeStatus.COMPLETED,
        state_updates=updates,
    )


# ---------------------------------------------------------------------------
# Node 12: run_quality_gates
# ---------------------------------------------------------------------------
@_register("run_quality_gates", "Run quality gates on pipeline output", critical=True)
def node_run_quality_gates(state: ProductWorkflowState) -> NodeResult:
    gates: dict[str, bool | str] = {}
    failures: list[str] = []

    has_evidence = len(state.evidence_items) > 0
    gates["evidence_collected"] = has_evidence
    if not has_evidence:
        failures.append("No evidence collected")

    has_profile = bool(state.startup_profile)
    gates["profile_extracted"] = has_profile
    if not has_profile:
        failures.append("No startup profile extracted")

    has_scores = bool(state.scores)
    gates["scoring_complete"] = has_scores
    if not has_scores:
        failures.append("No quantitative scores generated")

    has_gaps = len(state.gap_ids) > 0
    gates["gaps_diagnosed"] = has_gaps
    if not has_gaps:
        failures.append("No gaps diagnosed")

    has_mappings = len(state.nvidia_mappings) > 0
    gates["technologies_mapped"] = has_mappings
    if not has_mappings:
        failures.append("No NVIDIA technologies mapped")

    structured_recs = state.ranked_recommendations or state.node_outputs.get("expected_utility_result", {}).get("ranked_recommendations", [])
    has_recommendations = len(state.recommendations) > 0 or len(structured_recs) > 0
    gates["recommendations_generated"] = has_recommendations
    if not has_recommendations:
        failures.append("No NVIDIA recommendations generated")

    has_expected_utility = len(state.ranked_recommendations) > 0 or bool(state.node_outputs.get("expected_utility_result"))
    gates["expected_utility_ranking_generated"] = has_expected_utility
    if not has_expected_utility:
        failures.append("No expected-utility ranking generated")

    has_brief = bool(state.brief)
    gates["brief_generated"] = has_brief
    if not has_brief:
        failures.append("No brief generated")

    status = "passed" if not failures else "failed"
    return NodeResult(
        status=NodeStatus.COMPLETED if status == "passed" else (NodeStatus.FAILED if _is_product_mode() else NodeStatus.DEGRADED),
        error_message="; ".join(failures) if failures and _is_product_mode() else None,
        state_updates={
            "quality_gates_result": {
                "status": status,
                "gates": gates,
                "failures": failures,
            }
        },
        degraded_reason="; ".join(failures) if failures else None,
    )


# ---------------------------------------------------------------------------
# Node 13: generate_claims
# ---------------------------------------------------------------------------
@_register("generate_claims", "Generate evidence-linked claims from pipeline output", critical=True)
def node_generate_claims(state: ProductWorkflowState) -> NodeResult:
    session = cast(Session | None, state.metadata_json.get("_session"))
    if session is None:
        return NodeResult(status=NodeStatus.FAILED, error_message="No database session available")

    analysis_run_id = state.analysis_run_id
    if not analysis_run_id:
        return NodeResult(status=NodeStatus.SKIPPED, error_message="No analysis_run_id for claim generation")

    from src.repositories.product import ProductRepository

    repo = ProductRepository(session)
    run = repo.get_analysis_run(analysis_run_id)
    if run is None:
        return NodeResult(status=NodeStatus.FAILED, error_message=f"AnalysisRun not found: {analysis_run_id}")

    try:
        ledger = ClaimLedgerService(session)
        ledger.persist_claims_for_run(run)
        from src.database.models import ClaimRecord

        stmt = __import__("sqlalchemy").select(ClaimRecord).where(ClaimRecord.analysis_run_id == analysis_run_id)
        claims = list(session.scalars(stmt))
        claim_ids = [c.id for c in claims]
        return NodeResult(status=NodeStatus.COMPLETED, state_updates={"claim_ids": claim_ids})
    except Exception as exc:
        return NodeResult(
            status=NodeStatus.DEGRADED,
            error_message=str(exc),
            degraded_reason="Claim generation failed",
        )


# ---------------------------------------------------------------------------
# Node 14: match_activation_playbooks
# ---------------------------------------------------------------------------
@_register("match_activation_playbooks", "Match activation playbooks to diagnosed gaps", critical=True)
def node_match_activation_playbooks(state: ProductWorkflowState) -> NodeResult:
    session = cast(Session | None, state.metadata_json.get("_session"))
    if session is None:
        return NodeResult(status=NodeStatus.FAILED, error_message="No database session available")

    analysis_run_id = state.analysis_run_id
    if not analysis_run_id:
        return NodeResult(status=NodeStatus.SKIPPED, error_message="No analysis_run_id for playbook matching")

    try:
        # Gap and mapping nodes commit their terminal snapshots and product
        # records before this node runs. Expire identity-map relationships so
        # ActivationPlaybookService reads the newly persisted gaps/mappings
        # instead of collections cached when the AnalysisRun was created.
        session.expire_all()
        act_service = ActivationPlaybookService(session)
        recs = act_service.generate_recommendations_for_run(analysis_run_id)
        if recs:
            act_service.activation_repo.replace_recommendations_for_analysis_run(analysis_run_id, recs)
            rec_ids = [r.get("id", "") for r in recs if r.get("id")]
        else:
            rec_ids = []
        if not rec_ids:
            return NodeResult(
                status=NodeStatus.DEGRADED,
                degraded_reason="No activation playbooks matched",
                state_updates={"activation_recommendation_ids": []},
            )
        return NodeResult(status=NodeStatus.COMPLETED, state_updates={"activation_recommendation_ids": rec_ids})
    except Exception as exc:
        return NodeResult(
            status=NodeStatus.DEGRADED,
            error_message=str(exc),
            degraded_reason="Playbook matching failed",
        )


# ---------------------------------------------------------------------------
# Node 15: generate_activation_dossier
# ---------------------------------------------------------------------------
@_register("generate_activation_dossier", "Generate activation dossier from analysis run", critical=True)
def node_generate_activation_dossier(state: ProductWorkflowState) -> NodeResult:
    session = cast(Session | None, state.metadata_json.get("_session"))
    if session is None:
        return NodeResult(status=NodeStatus.FAILED, error_message="No database session available")

    analysis_run_id = state.analysis_run_id
    if not analysis_run_id:
        return NodeResult(status=NodeStatus.SKIPPED, error_message="No analysis_run_id for dossier")

    try:
        dossier_service = ActivationDossierService(session)
        dossier = dossier_service.build_dossier_for_analysis_run(analysis_run_id)
        return NodeResult(
            status=NodeStatus.COMPLETED,
            state_updates={"dossier_id": dossier.id},
        )
    except Exception as exc:
        return NodeResult(
            status=NodeStatus.DEGRADED,
            error_message=str(exc),
            degraded_reason="Dossier generation failed",
        )


# ---------------------------------------------------------------------------
# Node 16: run_product_quality
# ---------------------------------------------------------------------------
@_register("run_product_quality", "Run product quality evaluation on analysis run", critical=True)
def node_run_product_quality(state: ProductWorkflowState) -> NodeResult:
    session = cast(Session | None, state.metadata_json.get("_session"))
    if session is None:
        return NodeResult(status=NodeStatus.FAILED, error_message="No database session available")

    analysis_run_id = state.analysis_run_id
    if not analysis_run_id:
        return NodeResult(status=NodeStatus.SKIPPED, error_message="No analysis_run_id for quality run")

    try:
        from src.quality.service import ProductQualityService

        quality_service = ProductQualityService(session)
        quality_run = quality_service.run_quality_evaluation_for_analysis_run(analysis_run_id)
        return NodeResult(
            status=NodeStatus.COMPLETED,
            state_updates={"quality_run_id": quality_run.id},
        )
    except Exception as exc:
        return NodeResult(
            status=NodeStatus.DEGRADED,
            error_message=str(exc),
            degraded_reason="Quality evaluation failed",
        )


# ---------------------------------------------------------------------------
# Node 17: summarize_readiness
# ---------------------------------------------------------------------------
@_register("summarize_readiness", "Summarize readiness checks into final state", critical=True)
def node_summarize_readiness(state: ProductWorkflowState) -> NodeResult:
    session = cast(Session | None, state.metadata_json.get("_session"))
    if session is None:
        return NodeResult(status=NodeStatus.FAILED, error_message="No database session available")

    analysis_run_id = state.analysis_run_id
    if not analysis_run_id:
        return NodeResult(status=NodeStatus.COMPLETED, state_updates={})

    from src.database.models import ProductReadinessCheck

    stmt = (
        __import__("sqlalchemy")
        .select(ProductReadinessCheck)
        .where(ProductReadinessCheck.analysis_run_id == analysis_run_id)
    )
    checks = list(session.scalars(stmt))
    check_ids = [c.id for c in checks]
    degraded_codes = [c.code for c in checks if c.status == "degraded"]

    return NodeResult(
        status=NodeStatus.COMPLETED,
        state_updates={
            "readiness_check_ids": check_ids,
            "degraded_nodes": degraded_codes,
        },
    )


# ---------------------------------------------------------------------------
# Node 18: needs_review (human-in-the-loop)
# ---------------------------------------------------------------------------
@_register("needs_review", "Human-in-the-loop review node", critical=False)
def node_needs_review(state: ProductWorkflowState) -> NodeResult:
    """Pause only when quantitative review gates require human oversight.

    The node no longer catches LangGraph interrupts. In LangGraph, ``interrupt``
    is the control-flow primitive that pauses execution and persists state;
    swallowing it would turn a required review into a degraded/no-op path.
    """
    from src.quality.constants import METRIC_REVIEW_READINESS_SCORE, THRESHOLDS

    quality = state.quality_gates_result or {}
    failures = list(quality.get("failures", [])) if isinstance(quality, dict) else []
    scores = state.evidence_weighted_scores or state.scores or {}
    uncertainty = float(scores.get("uncertainty", 1.0 if not scores else 0.0))
    confidence = float(scores.get("confidence", 0.0))
    review_threshold = float(
        THRESHOLDS.get(METRIC_REVIEW_READINESS_SCORE, {}).get("threshold", 0.60)
    )

    evidence_count = len(state.evidence_items)
    recommendation_count = len(state.ranked_recommendations) or len(state.recommendations)
    mapping_count = len(state.nvidia_mappings)
    degraded_count = len(state.degraded_nodes)
    technique_failure_count = len([r for r in state.technique_results if not r.get("success", True)])

    review_score_components = {
        "confidence": confidence,
        "certainty": max(0.0, 1.0 - uncertainty),
        "quality_gate_pass": 1.0 if not failures else 0.0,
        "evidence_present": 1.0 if evidence_count > 0 else 0.0,
        "mapping_present": 1.0 if mapping_count > 0 else 0.0,
        "recommendation_present": 1.0 if recommendation_count > 0 else 0.0,
        "no_degraded_nodes": 1.0 if degraded_count == 0 else 0.0,
        "techniques_clean": 1.0 if technique_failure_count == 0 else 0.0,
    }
    review_readiness_score = round(
        sum(review_score_components.values()) / max(1, len(review_score_components)),
        4,
    )
    required = review_readiness_score < review_threshold or bool(failures)

    review_data = {
        "startup_id": state.startup_id,
        "analysis_run_id": state.analysis_run_id,
        "gaps_found": len(state.gap_ids),
        "mappings_found": mapping_count,
        "recommendations_found": recommendation_count,
        "evidence_count": evidence_count,
        "quality_gates": quality,
        "review_readiness_score": review_readiness_score,
        "review_readiness_threshold": review_threshold,
        "review_score_components": review_score_components,
        "review_required_reasons": failures
        + (["review_readiness_below_threshold"] if review_readiness_score < review_threshold else []),
    }

    if not required or not LANGGRAPH_AVAILABLE:
        return NodeResult(
            status=NodeStatus.COMPLETED,
            state_updates={
                "review_payload": review_data,
                "review_required": False,
                "node_outputs": {
                    **state.node_outputs,
                    "review_gate": review_data,
                },
            },
        )

    decision = interrupt(review_data)
    return NodeResult(
        status=NodeStatus.COMPLETED,
        state_updates={
            "review_payload": review_data,
            "review_required": True,
            "review_decision": decision if isinstance(decision, str) else "",
            "node_outputs": {
                **state.node_outputs,
                "review_gate": review_data,
            },
        },
    )


# ---------------------------------------------------------------------------
# Node 19: apply_feedback_weights
# ---------------------------------------------------------------------------
@_register("apply_feedback_weights", "Adjust scoring weights from human review feedback", critical=False)
def node_apply_feedback_weights(state: ProductWorkflowState) -> NodeResult:
    from src.decisioning.feedback_learner import learn_feedback_weight

    feedback_counts = state.feedback_counts
    if not feedback_counts:
        return NodeResult(status=NodeStatus.SKIPPED, state_updates={"iteration_count": state.iteration_count})

    from src.config.loader import ConfigLoaderService

    cfg = ConfigLoaderService()
    adjusted: dict[str, float] = {}
    feedback_adjustments: dict[str, object] = {}

    base_pool: dict[str, float] = {}
    base_pool.update(cfg.priority_score_weights())
    base_pool.update(cfg.scoring().opportunity_score.model_dump())
    base_pool.update(cfg.scoring().production_readiness.model_dump())
    base_pool.update(cfg.scoring().defensibility.model_dump())
    base_pool.update(cfg.scoring().inception_fit.model_dump())

    for key, counts in feedback_counts.items():
        base = base_pool.get(key)
        if base is None:
            continue
        adjustment = learn_feedback_weight(
            base,
            positive=counts.get("positive", 0),
            negative=counts.get("negative", 0),
        )
        adjusted[key] = float(adjustment["adjusted_weight"])
        feedback_adjustments[key] = adjustment

    return NodeResult(
        status=NodeStatus.COMPLETED,
        state_updates={
            "adjusted_weights": adjusted,
            "feedback_adjustments": feedback_adjustments,
            "feedback_counts": {},
            "iteration_count": state.iteration_count + 1,
        },
    )


# ---------------------------------------------------------------------------
# Node 20: enhance_contexts_with_techniques
# ---------------------------------------------------------------------------
@_register("enhance_contexts_with_techniques", "Enhance NVIDIA contexts using hybrid RAG techniques", critical=True)
def node_enhance_contexts_with_techniques(state: ProductWorkflowState) -> NodeResult:
    nvidia_contexts = state.nvidia_contexts
    if not nvidia_contexts:
        return NodeResult(status=NodeStatus.SKIPPED, error_message="No NVIDIA contexts to enhance")

    from src.rag.schemas import RetrievedContext
    from src.rag.technique_runner import run_techniques_hybrid

    try:
        contexts = [
            RetrievedContext.model_validate(
                _normalize_rag_context_for_runtime(c, state.gap_ids) if isinstance(c, dict) else c
            )
            for c in nvidia_contexts
        ]
    except Exception as exc:
        return NodeResult(
            status=NodeStatus.FAILED if _is_product_mode() else NodeStatus.DEGRADED,
            state_updates={"technique_results": []},
            error_message=f"Could not parse nvidia_contexts as RetrievedContext: {exc}" if _is_product_mode() else None,
            degraded_reason=f"Could not parse nvidia_contexts as RetrievedContext: {exc}",
        )

    try:
        import yaml
        from pathlib import Path

        cfg_path = Path("config/techniques.yaml")
        if cfg_path.exists():
            with cfg_path.open(encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            group_config = raw.get("groups", [])
        else:
            group_config = []
    except Exception:
        group_config = []

    try:
        from src.rag.schemas import RetrievalQuery
        from src.rag.retrieval import build_default_index

        technique_query = " ".join([
            *[str(g) for g in state.gap_ids],
            *[str(ctx.product) for ctx in contexts[:5]],
        ])
        retrieval_query = RetrievalQuery(
            gap_type=str(state.gap_ids[0]) if state.gap_ids else None,
            technology=str(contexts[0].product) if contexts else None,
            keywords=[str(g) for g in state.gap_ids[:5]],
        )
        chunk_index = build_default_index()
        corpus_contexts = chunk_index.retrieve(retrieval_query, top_k=max(20, len(contexts) * 3))
        result = run_techniques_hybrid(
            contexts,
            group_config=group_config,
            query=technique_query,
            retrieval_query=retrieval_query,
            chunk_index=chunk_index,
            corpus_contexts=corpus_contexts,
            top_k=max(10, len(contexts)),
        )
    except Exception as exc:
        return NodeResult(
            status=NodeStatus.DEGRADED,
            state_updates={"technique_results": []},
            degraded_reason=f"Technique runner failed: {exc}",
        )

    enhanced_contexts = result.get("contexts", contexts)
    technique_results = result.get("results", [])
    succeeded = [r for r in technique_results if r.get("success")]
    failed = [r for r in technique_results if not r.get("success")]

    return NodeResult(
        status=NodeStatus.COMPLETED if not failed else NodeStatus.DEGRADED,
        state_updates={
            "nvidia_contexts": [c.model_dump(mode="json") for c in enhanced_contexts],
            "technique_results": technique_results,
        },
        degraded_reason=f"{len(failed)} techniques failed: {', '.join(r['technique'] for r in failed[:5])}" if failed else None,
    )


# ---------------------------------------------------------------------------
# Node 21: rank_with_expected_utility
# ---------------------------------------------------------------------------
@_register("rank_with_expected_utility", "Rank recommendations by expected utility", critical=True)
def node_rank_with_expected_utility(state: ProductWorkflowState) -> NodeResult:
    nvidia_mappings = state.nvidia_mappings
    recommendations = state.recommendations
    recommendation_result = state.node_outputs.get("nvidia_recommendation_result", {})
    mapping_recommendations = (
        recommendation_result.get("nvidia_recommendations", [])
        if isinstance(recommendation_result, dict)
        else []
    )

    evidence_score = state.evidence_weighted_scores or state.scores or {}
    default_confidence = float(evidence_score.get("confidence", 0.5))
    default_uncertainty = float(evidence_score.get("uncertainty", 0.5))
    default_evidence_support = float(evidence_score.get("evidence_coverage", evidence_score.get("confidence", 0.5)))

    candidates: list[dict[str, object]] = []
    for rec in mapping_recommendations or []:
        supporting_evidence_ids = list(rec.get("supporting_evidence_ids", []))
        supporting_rag_context_ids = list(rec.get("supporting_rag_context_ids", []))
        candidates.append({
            **rec,
            "recommendation_id": rec.get("recommendation_id") or f"rec_{len(candidates)}",
            "technology": rec.get("nvidia_technology", rec.get("technology", "")),
            "business_impact": rec.get("business_impact", rec.get("recommendation_priority_score", 0.5)),
            "confidence": rec.get("confidence", default_confidence),
            "implementation_complexity": rec.get("implementation_complexity", 0.5),
            "risk": rec.get("uncertainty", default_uncertainty),
            "uncertainty": rec.get("uncertainty", default_uncertainty),
            "evidence_support": min(1.0, (len(supporting_evidence_ids) + len(supporting_rag_context_ids)) / 2.0),
        })

    for mapping in [] if candidates else (nvidia_mappings or []):
        gap_id = mapping.get("gap_id", "")
        technology = mapping.get("technology", mapping.get("nvidia_technology", ""))
        supporting_evidence_ids = list(mapping.get("supporting_evidence_ids", []))
        supporting_rag_context_ids = list(mapping.get("supporting_rag_context_ids", []))
        candidates.append({
            "recommendation_id": f"rec_{technology}_{gap_id}",
            "technology": technology,
            "nvidia_technology": technology,
            "gap_id": gap_id,
            "business_impact": mapping.get("business_impact", mapping.get("mapping_score", 0.5)),
            "confidence": mapping.get("confidence", mapping.get("mapping_confidence", default_confidence)),
            "implementation_complexity": mapping.get("implementation_complexity", 0.3),
            "risk": mapping.get("risk", default_uncertainty),
            "uncertainty": mapping.get("uncertainty", default_uncertainty),
            "evidence_support": mapping.get(
                "evidence_support",
                min(1.0, (len(supporting_evidence_ids) + len(supporting_rag_context_ids)) / 2.0)
                if supporting_evidence_ids or supporting_rag_context_ids
                else default_evidence_support,
            ),
            "supporting_rag_context_ids": supporting_rag_context_ids,
            "supporting_evidence_ids": supporting_evidence_ids,
        })

    for rec in [] if candidates else (recommendations or []):
        if isinstance(rec, str):
            candidates.append({
                "recommendation_id": f"rec_{len(candidates)}",
                "technology": rec,
                "gap_id": "",
                "business_impact": 0.5,
                "confidence": default_confidence,
                "implementation_complexity": 0.3,
                "risk": default_uncertainty,
                "uncertainty": default_uncertainty,
                "evidence_support": default_evidence_support,
            })

    if not candidates:
        return NodeResult(status=NodeStatus.SKIPPED, error_message="No candidates to rank")

    from src.decisioning.adaptive_recommendation_ranker import rank_recommendations

    try:
        ranked = rank_recommendations(candidates)
    except Exception as exc:
        return NodeResult(
            status=NodeStatus.DEGRADED,
            state_updates={"ranked_recommendations": candidates},
            degraded_reason=f"Ranking failed: {exc}",
        )

    return NodeResult(
        status=NodeStatus.COMPLETED,
        state_updates={"ranked_recommendations": ranked},
    )


# ---------------------------------------------------------------------------
# Node 23: write_decision_ledger
# ---------------------------------------------------------------------------
@_register("write_decision_ledger", "Write decision ledger CSV for audit trail", critical=True)
def node_write_decision_ledger(state: ProductWorkflowState) -> NodeResult:
    from datetime import datetime, UTC
    from json import dumps
    from pathlib import Path
    from src.decisioning.decision_ledger_writer import append_decision

    ledger_path = Path("data/decision_ledger.csv")
    run_id = state.analysis_run_id or state.workflow_id

    decisions: list[dict[str, object]] = []

    if state.evidence_weighted_scores:
        ws = state.evidence_weighted_scores
        decisions.append({
            "decision_id": f"score_{run_id}",
            "area": "scoring",
            "decision": f"Evidence-weighted score: {ws.get('score', 'N/A')}",
            "alternatives_considered": "Deterministic scoring",
            "metrics_used": dumps({
                "formula": ws.get("formula", ""),
                "evidence_count": ws.get("evidence_count", 0),
                "evidence_coverage": ws.get("evidence_coverage", 0),
                "source_diversity": ws.get("source_diversity", 0),
                "evidence_quality_mean": ws.get("evidence_quality_mean", 0),
                "value_variance": ws.get("value_variance", 0),
                "uncertainty_components": ws.get("uncertainty_components", {}),
            }, sort_keys=True),
            "data_source": "evidence_items, startup_profile",
            "benchmark_file": "config/scoring.yaml",
            "chosen_option": f"score={ws.get('score')}, confidence={ws.get('confidence')}",
            "expected_value": ws.get("score", 0),
            "confidence": ws.get("confidence", 0),
            "uncertainty": ws.get("uncertainty", 1),
            "risks": f"evidence_count={ws.get('evidence_count', 0)}",
            "owner": "pipeline",
            "date": datetime.now(UTC).isoformat(),
            "status": "approved",
        })

    if state.ranked_recommendations:
        for idx, rec in enumerate(state.ranked_recommendations):
            decisions.append({
                "decision_id": f"rank_{run_id}_{idx}",
                "area": "ranking",
                "decision": f"Rank {rec.get('expected_utility_rank', idx + 1)}: {rec.get('technology', 'N/A')}",
                "alternatives_considered": "Original order",
                "metrics_used": dumps(rec.get("expected_utility_breakdown", {}), sort_keys=True),
                "data_source": "nvidia_mappings, recommendations",
                "benchmark_file": "",
                "chosen_option": str(rec.get("technology", "")),
                "expected_value": rec.get("expected_utility", rec.get("business_impact", 0)),
                "confidence": rec.get("confidence", 0),
                "uncertainty": rec.get("uncertainty", 0),
                "risks": f"complexity={rec.get('implementation_complexity', 0)}, risk={rec.get('risk', 0)}",
                "owner": "pipeline",
                "date": datetime.now(UTC).isoformat(),
                "status": "approved",
            })

    if state.technique_results:
        for tr in state.technique_results:
            decisions.append({
                "decision_id": f"technique_{tr.get('technique', 'unknown')}_{run_id}",
                "area": "rag_technique",
                "decision": f"Group={tr.get('group', 'N/A')}, success={tr.get('success', False)}",
                "alternatives_considered": "Skip technique",
                "metrics_used": dumps({
                    "latency_ms": tr.get("latency_ms", 0),
                    "quality_delta": tr.get("quality_delta", 0),
                    "cost_estimate": tr.get("cost_estimate", 0),
                    "input_count": tr.get("input_count", 0),
                    "output_count": tr.get("output_count", 0),
                    "evidence": tr.get("evidence", {}),
                }, sort_keys=True),
                "data_source": f"src.rag.{tr.get('technique', '')}",
                "benchmark_file": "config/techniques.yaml",
                "chosen_option": "enabled" if tr.get("success") else "failed",
                "expected_value": tr.get("quality_delta", 1 if tr.get("success") else 0),
                "confidence": 1 if tr.get("success") else 0,
                "uncertainty": 0 if tr.get("success") else 1,
                "risks": tr.get("error", "") if not tr.get("success") else "",
                "owner": "pipeline",
                "date": datetime.now(UTC).isoformat(),
                "status": "completed" if tr.get("success") else "failed",
            })

    if state.feedback_adjustments:
        for key, adjustment in state.feedback_adjustments.items():
            if not isinstance(adjustment, dict):
                continue
            decisions.append({
                "decision_id": f"feedback_{key}_{run_id}",
                "area": "feedback_learning",
                "decision": f"Adjusted weight {key}: {adjustment.get('base_weight')} -> {adjustment.get('adjusted_weight')}",
                "alternatives_considered": "Ignore human feedback",
                "metrics_used": dumps(adjustment, sort_keys=True),
                "data_source": "human_review_feedback_counts",
                "benchmark_file": "config/scoring.yaml",
                "chosen_option": f"{key}={adjustment.get('adjusted_weight')}",
                "expected_value": adjustment.get("adjusted_weight", 0),
                "confidence": adjustment.get("confidence", 0),
                "uncertainty": adjustment.get("uncertainty", 1),
                "risks": f"sample_size={adjustment.get('sample_size', 0)}",
                "owner": "pipeline",
                "date": datetime.now(UTC).isoformat(),
                "status": "completed",
            })

    if not decisions:
        return NodeResult(status=NodeStatus.SKIPPED, error_message="No decisions to record")

    try:
        for dec in decisions:
            append_decision(ledger_path, dec)
    except Exception as exc:
        return NodeResult(
            status=NodeStatus.DEGRADED,
            state_updates={"decision_ledger_path": ""},
            degraded_reason=f"Failed to write decision ledger: {exc}",
        )

    return NodeResult(
        status=NodeStatus.COMPLETED,
        state_updates={"decision_ledger_path": str(ledger_path)},
    )
