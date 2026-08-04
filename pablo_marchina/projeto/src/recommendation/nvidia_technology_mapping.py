from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from src.diagnosis.schemas import GapDiagnosisMetrics, GapDiagnosisResultItem
from src.quality.decision_calibration_registry import (
    DecisionCalibrationRecord,
    get_project_decision_inventory,
    validate_decision_for_production,
)


class NvidiaMappingStatus(str, Enum):
    PASSED = "passed"
    NEEDS_REVIEW = "needs_review"
    BLOCKED_UNCALIBRATED_MAPPING = "blocked_uncalibrated_mapping"
    FAILED = "failed"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"


class NvidiaTechnologyMappingRecord(BaseModel):
    mapping_id: str
    gap_type: str
    nvidia_technology: str
    technology_category: str = ""
    required_gap_features: list[str] = Field(default_factory=list)
    required_rag_topics: list[str] = Field(default_factory=list)
    required_evidence_types: list[str] = Field(default_factory=list)
    mapping_score: float = Field(default=0.0, ge=0.0, le=1.0)
    mapping_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    uncertainty: float = Field(default=1.0, ge=0.0, le=1.0)
    supporting_rag_context_ids: list[str] = Field(default_factory=list)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    calibration_decision_ids: list[str] = Field(default_factory=list)
    production_allowed: bool = False
    blockers: list[str] = Field(default_factory=list)
    explanation: str = ""


class NvidiaMappingFeatures(BaseModel):
    gap_severity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    gap_confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    rag_context_count_for_technology: float = Field(default=0.0, ge=0.0, le=1.0)
    rag_relevance_mean_for_technology: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_support_count: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_confidence_mean: float = Field(default=0.0, ge=0.0, le=1.0)
    source_quality_mean: float = Field(default=0.0, ge=0.0, le=1.0)
    technology_topic_match_count: float = Field(default=0.0, ge=0.0, le=1.0)
    startup_profile_signal_match_count: float = Field(default=0.0, ge=0.0, le=1.0)
    uncertainty_penalty: float = Field(default=0.0, ge=0.0, le=1.0)


class NvidiaMappingConfidenceFeatures(BaseModel):
    supporting_rag_context_count: float = Field(default=0.0, ge=0.0, le=1.0)
    supporting_evidence_count: float = Field(default=0.0, ge=0.0, le=1.0)
    average_rag_relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    average_evidence_confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    cross_source_support_count: float = Field(default=0.0, ge=0.0, le=1.0)
    contradiction_count: float = Field(default=0.0, ge=0.0, le=1.0)
    corpus_payload_completeness_rate: float = Field(default=0.0, ge=0.0, le=1.0)


class NvidiaMappingMetrics(BaseModel):
    total_mapping_count: int = Field(default=0, ge=0)
    production_allowed_mapping_count: int = Field(default=0, ge=0)
    blocked_mapping_count: int = Field(default=0, ge=0)
    mappings_by_gap_type: dict[str, int] = Field(default_factory=dict)
    mappings_by_technology: dict[str, int] = Field(default_factory=dict)
    average_mapping_score: float = Field(default=0.0, ge=0.0, le=1.0)
    average_mapping_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    unsupported_mapping_count: int = Field(default=0, ge=0)
    missing_calibration_count: int = Field(default=0, ge=0)
    rag_supported_mapping_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_supported_mapping_rate: float = Field(default=0.0, ge=0.0, le=1.0)


class NvidiaMappingCalibrationMetrics(BaseModel):
    mapping_precision_at_k: float = 0.0
    mapping_recall_at_k: float = 0.0
    mapping_mrr: float = 0.0
    false_positive_mapping_rate: float = 0.0
    evidence_supported_mapping_rate: float = 0.0
    rag_supported_mapping_rate: float = 0.0
    unsupported_mapping_rate: float = 0.0
    technology_coverage: float = 0.0


class GoldenMappingSample(BaseModel):
    gap_id: str
    gap_type: str
    gap_features_snapshot: dict[str, Any] = Field(default_factory=dict)
    rag_contexts_snapshot: list[dict[str, Any]] = Field(default_factory=list)
    evidence_items_snapshot: list[dict[str, Any]] = Field(default_factory=list)
    expected_nvidia_technologies: list[str] = Field(default_factory=list)
    human_label_mapping_relevance: str = "low"
    reviewer_id: str = ""
    label_notes: str = ""


# ---------------------------------------------------------------------------
# Static candidate mapping matrix (gap_type -> candidate technologies)
# production_allowed=false, calibration_status="candidate"
# ---------------------------------------------------------------------------

NVIDIA_TECHNOLOGIES: dict[str, str] = {
    "NVIDIA Inception": "startup_program",
    "NVIDIA API Catalog": "model_api_catalog",
    "CUDA": "compute",
    "TensorRT": "inference_optimization",
    "TensorRT-LLM": "llm_inference_optimization",
    "Triton Inference Server": "inference_serving",
    "NVIDIA NIM": "inference_microservices",
    "NVIDIA NeMo": "llm_framework",
    "NeMo Guardrails": "agent_governance",
    "RAPIDS": "data_pipeline",
    "cuDF": "gpu_dataframe",
    "cuML": "gpu_machine_learning",
    "NVIDIA Riva": "speech_ai",
    "NVIDIA Omniverse": "simulation_digital_twin",
    "NVIDIA Isaac": "robotics",
    "NVIDIA Clara": "healthcare",
    "MONAI": "medical_ai_framework",
    "NVIDIA Morpheus": "cybersecurity",
    "NVIDIA AI Enterprise": "enterprise_platform",
    "NVIDIA AI Blueprints": "reference_architecture",
}

GAP_TECHNOLOGY_CANDIDATES: dict[str, list[str]] = {
    "compute_acceleration_gap": ["CUDA", "NVIDIA AI Enterprise", "NVIDIA Inception"],
    "inference_performance_gap": ["TensorRT-LLM", "TensorRT", "Triton Inference Server", "NVIDIA NIM"],
    "training_scalability_gap": ["CUDA", "NVIDIA NeMo", "NVIDIA AI Enterprise"],
    "mlops_deployment_gap": ["Triton Inference Server", "NVIDIA NIM", "NVIDIA AI Enterprise", "NVIDIA AI Blueprints"],
    "data_pipeline_gap": ["RAPIDS", "cuDF", "cuML", "CUDA"],
    "model_optimization_gap": ["TensorRT-LLM", "TensorRT", "NVIDIA NeMo", "NVIDIA NIM"],
    "computer_vision_gap": ["TensorRT", "NVIDIA NIM", "NVIDIA AI Enterprise", "NVIDIA API Catalog"],
    "genai_llm_gap": ["NVIDIA NIM", "NVIDIA NeMo", "NeMo Guardrails", "TensorRT-LLM", "NVIDIA API Catalog"],
    "agent_governance_gap": ["NeMo Guardrails", "NVIDIA NeMo", "NVIDIA AI Blueprints", "NVIDIA AI Enterprise"],
    "cybersecurity_ai_gap": ["NVIDIA Morpheus", "NVIDIA AI Enterprise"],
    "healthcare_compliance_need": ["NVIDIA Clara", "MONAI", "NVIDIA AI Enterprise", "NeMo Guardrails"],
    "voice_need": ["NVIDIA Riva", "NVIDIA NIM"],
    "simulation_need": ["NVIDIA Omniverse", "NVIDIA Isaac"],
    "robotics_need": ["NVIDIA Isaac", "NVIDIA Omniverse", "NVIDIA AI Enterprise"],
    "nvidia_ecosystem_fit_gap": ["NVIDIA Inception", "NVIDIA AI Enterprise", "NVIDIA API Catalog", "NVIDIA NIM", "CUDA"],
    "startup_program_fit_gap": ["NVIDIA Inception"],
    "go_to_market_gap": ["NVIDIA Inception", "NVIDIA AI Enterprise"],
    "evidence_coverage_gap": ["NVIDIA Inception"],
    "technical_depth_gap": ["NVIDIA AI Blueprints", "NVIDIA API Catalog", "NVIDIA Inception"],
}


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _compute_weighted_score(
    features: dict[str, float],
    weights: dict[str, float],
) -> float:
    weight_sum = sum(weights.values())
    if weight_sum == 0.0:
        return 0.0
    raw = sum(weights.get(k, 0.0) * v for k, v in features.items() if k in weights)
    raw /= weight_sum
    return max(0.0, min(1.0, raw))


def _lookup_calibration_group(
    decision_ids: list[str],
    inventory: list[DecisionCalibrationRecord] | None = None,
) -> tuple[dict[str, Any] | None, bool, list[str]]:
    if inventory is None:
        inventory = get_project_decision_inventory()
    values: dict[str, Any] = {}
    blockers: list[str] = []
    for decision_id in decision_ids:
        found = False
        for rec in inventory:
            if rec.decision_id == decision_id:
                found = True
                validation = validate_decision_for_production(rec)
                if not validation.passed:
                    blockers.append(f"Decision '{decision_id}' blocked for production: {'; '.join(validation.reasons)}")
                elif rec.calibration_status.value in ("uncalibrated", "blocked"):
                    blockers.append(f"Decision '{decision_id}' is {rec.calibration_status.value}")
                else:
                    values[decision_id] = rec.current_value
                break
        if not found:
            blockers.append(f"Decision '{decision_id}' not found in registry")
    if blockers:
        return None, False, blockers
    return values, True, []


def _lookup_weight_dict(
    decision_id: str,
    values: dict[str, Any],
) -> dict[str, float] | None:
    v = values.get(decision_id)
    if isinstance(v, dict):
        result: dict[str, float] = {}
        for k, val in v.items():
            if isinstance(val, (int, float)):
                result[k] = float(val)
        return result
    return None


def _lookup_float(
    decision_id: str,
    values: dict[str, Any],
) -> float | None:
    v = values.get(decision_id)
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _lookup_int(
    decision_id: str,
    values: dict[str, Any],
) -> int | None:
    v = values.get(decision_id)
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return None


def _text_contains_any(text: str, keywords: list[str]) -> bool:
    lower = text.casefold()
    return any(kw.casefold() in lower for kw in keywords if kw)


def _evidence_text(item: dict[str, Any]) -> str:
    return str(
        item.get("text")
        or item.get("quote_or_evidence")
        or item.get("snippet")
        or item.get("claim")
        or ""
    )


def _evidence_id(item: dict[str, Any]) -> str:
    return str(item.get("id") or item.get("evidence_id") or "")


# ---------------------------------------------------------------------------
# Required calibration decisions for mapping
# ---------------------------------------------------------------------------

REQUIRED_MAPPING_DECISIONS: list[str] = [
    "nvidia_mapping.mapping_score_weights",
    "nvidia_mapping.mapping_confidence_weights",
    "nvidia_mapping.production_threshold",
    "nvidia_mapping.minimum_rag_contexts",
    "nvidia_mapping.minimum_evidence_support",
    "nvidia_mapping.uncertainty_penalty",
    "nvidia_mapping.technology_priority_policy",
]


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------


def extract_mapping_features(
    gap_type: str,
    technology: str,
    rag_contexts: list[dict[str, Any]],
    evidence_items: list[dict[str, Any]],
    gap_result: GapDiagnosisResultItem | None,
) -> tuple[NvidiaMappingFeatures, NvidiaMappingConfidenceFeatures]:
    # ── Score features ──────────────────────────────────────────────────
    gap_severity = gap_result.severity_score if gap_result else 0.5
    gap_confidence = gap_result.confidence_score if gap_result else 0.5

    rag_for_tech = [ctx for ctx in rag_contexts if _context_matches_technology(ctx, technology)]
    rag_context_count = len(rag_for_tech)
    rag_relevance_scores = [
        float(ctx.get("relevance_score", 0.0))
        for ctx in rag_for_tech
        if isinstance(ctx.get("relevance_score"), (int, float))
    ]
    rag_relevance_mean = _mean(rag_relevance_scores)

    # Company evidence proves the diagnosed need; governed NVIDIA RAG contexts
    # prove that a technology addresses that need. Requiring the company source
    # to already name the recommended NVIDIA product would make novel
    # recommendations impossible and would conflate adoption with suitability.
    gap_support_ids = set(gap_result.supporting_evidence_ids if gap_result else [])
    ev_for_tech = [item for item in evidence_items if _evidence_id(item) in gap_support_ids]
    evidence_count = len(ev_for_tech)

    ev_confidences: list[float] = []
    ev_qualities: list[float] = []
    for item in ev_for_tech:
        ec = item.get("evidence_confidence_score", item.get("extraction_confidence"))
        if isinstance(ec, (int, float)):
            ev_confidences.append(float(ec))
        elif isinstance(item.get("confidence"), str):
            ev_confidences.append({"high": 1.0, "medium": 0.6, "low": 0.3}.get(str(item["confidence"]).casefold(), 0.0))
        sq = item.get("source_quality_score")
        if isinstance(sq, (int, float)):
            ev_qualities.append(float(sq))
    evidence_confidence_mean = _mean(ev_confidences)
    source_quality_mean = _mean(ev_qualities)

    topic_keywords = [technology.lower()] + _TECHNOLOGY_TOPIC_KEYWORDS.get(technology, [])
    all_text = " ".join(str(ctx.get("content", "") or ctx.get("title", "")) for ctx in rag_contexts)
    tech_topic_match = 1.0 if _text_contains_any(all_text, topic_keywords) else 0.0

    startup_keywords = ["gpu", "cuda", "deep learning", "machine learning", "ai"]
    startup_text = " ".join(_evidence_text(item) for item in evidence_items)
    signal_match_count = sum(1 for kw in startup_keywords if kw in startup_text.lower())
    _MAX_SIGNALS = 6.0
    startup_signal_norm = min(1.0, signal_match_count / _MAX_SIGNALS)

    uncertainty_penalty = 0.0
    if rag_context_count == 0 and evidence_count == 0:
        uncertainty_penalty = 0.5
    elif rag_context_count == 0 or evidence_count == 0:
        uncertainty_penalty = 0.2
    elif rag_context_count < 2 and evidence_count < 2:
        uncertainty_penalty = 0.1

    _MAX_RAG = 10.0
    _MAX_EVIDENCE = 10.0

    score_features = NvidiaMappingFeatures(
        gap_severity_score=gap_severity,
        gap_confidence_score=gap_confidence,
        rag_context_count_for_technology=round(min(1.0, rag_context_count / _MAX_RAG), 4),
        rag_relevance_mean_for_technology=round(rag_relevance_mean, 4),
        evidence_support_count=round(min(1.0, evidence_count / _MAX_EVIDENCE), 4),
        evidence_confidence_mean=round(evidence_confidence_mean, 4),
        source_quality_mean=round(source_quality_mean, 4),
        technology_topic_match_count=round(tech_topic_match, 4),
        startup_profile_signal_match_count=round(startup_signal_norm, 4),
        uncertainty_penalty=round(uncertainty_penalty, 4),
    )

    # ── Confidence features ─────────────────────────────────────────────
    source_ids: set[str] = set()
    for ctx in rag_for_tech:
        sid = ctx.get("source_id") or ctx.get("url", "")
        if sid:
            source_ids.add(sid)
    for item in ev_for_tech:
        sid = item.get("source_id") or item.get("source_url") or item.get("url", "")
        if sid:
            source_ids.add(sid)
    cross_source_count = min(1.0, len(source_ids) / 5.0)

    contradiction_count = min(
        1.0,
        sum(1 for c in rag_for_tech if isinstance(c.get("gap_types"), list) and len(c["gap_types"]) == 0) / 3.0,
    )

    completeness_rate = 1.0
    if rag_for_tech:
        has_content = sum(1 for ctx in rag_for_tech if ctx.get("content") and ctx.get("source_id"))
        completeness_rate = has_content / len(rag_for_tech)

    _MAX_RAG_CONF = 10.0
    _MAX_EV_CONF = 10.0

    conf_features = NvidiaMappingConfidenceFeatures(
        supporting_rag_context_count=round(min(1.0, rag_context_count / _MAX_RAG_CONF), 4),
        supporting_evidence_count=round(min(1.0, evidence_count / _MAX_EV_CONF), 4),
        average_rag_relevance_score=round(rag_relevance_mean, 4),
        average_evidence_confidence_score=round(evidence_confidence_mean, 4),
        cross_source_support_count=round(cross_source_count, 4),
        contradiction_count=round(contradiction_count, 4),
        corpus_payload_completeness_rate=round(completeness_rate, 4),
    )

    return score_features, conf_features


def _context_matches_technology(
    ctx: dict[str, Any],
    technology: str,
) -> bool:
    product = str(ctx.get("product", "") or ctx.get("nvidia_technology", "") or "")
    title = str(ctx.get("title", "") or "")
    content = str(ctx.get("content", "") or "")

    tech_lower = technology.lower()
    if tech_lower in product.lower():
        return True
    if tech_lower in title.lower():
        return True
    if tech_lower in content.lower():
        return True
    tech_short = technology.replace("nvidia ", "").strip().lower()
    if tech_short and tech_short != tech_lower and tech_short in product.lower():
        return True
    return False


_TECHNOLOGY_TOPIC_KEYWORDS: dict[str, list[str]] = {
    "CUDA": ["gpu computing", "parallel computing", "cuda cores", "gpu acceleration"],
    "TensorRT": ["inference optimization", "model optimization", "tensorrt", "int8 quantization"],
    "Triton Inference Server": ["model serving", "inference server", "multi-model serving"],
    "NVIDIA NIM": ["nim microservice", "inference microservice", "nim"],
    "NVIDIA NeMo": ["large language model", "llm", "nemo", "generative ai"],
    "RAPIDS": ["data pipeline", "gpu dataframe", "cudf", "cuml", "etl acceleration"],
    "NVIDIA Riva": ["speech recognition", "text to speech", "riva", "voice ai"],
    "NVIDIA Omniverse": ["digital twin", "simulation", "omniverse", "3d simulation"],
    "NVIDIA Isaac": ["robotics", "isaac sim", "robot simulation"],
    "NVIDIA Clara": ["healthcare", "medical imaging", "clara"],
    "NVIDIA Morpheus": ["cybersecurity", "threat detection", "morpheus", "security ai"],
    "NVIDIA AI Enterprise": ["enterprise ai", "ai platform", "nvidia ai enterprise"],
}


# ---------------------------------------------------------------------------
# Golden set / baseline
# ---------------------------------------------------------------------------

GOLDEN_MAPPING_SAMPLES: list[GoldenMappingSample] = []

GOLDEN_SET_STATUS = "baseline_dataset_measured"


# ---------------------------------------------------------------------------
# Main mapping function
# ---------------------------------------------------------------------------


def build_nvidia_technology_mappings(
    run_id: str,
    rag_contexts_by_gap: dict[str, list[dict[str, Any]]],
    gap_results: list[GapDiagnosisResultItem],
    gap_metrics: GapDiagnosisMetrics | None,
    evidence_items: list[dict[str, Any]],
    inventory: list[DecisionCalibrationRecord] | None = None,
) -> dict[str, Any]:
    if inventory is None:
        inventory = get_project_decision_inventory()

    # ── Calibration gate ────────────────────────────────────────────────
    cal_values, cal_ok, blockers = _lookup_calibration_group(REQUIRED_MAPPING_DECISIONS, inventory=inventory)
    is_blocked = not cal_ok

    # ── Golden set gate ─────────────────────────────────────────────────
    if GOLDEN_SET_STATUS == "baseline_dataset_insufficient":
        is_blocked = True
        blockers.append(
            "Golden set status is 'baseline_dataset_insufficient': "
            "no labeled mapping samples available for calibration."
        )

    # ── Build gap_type -> gap_result lookup ─────────────────────────────
    gap_result_by_type: dict[str, GapDiagnosisResultItem] = {}
    for g in gap_results:
        gap_result_by_type[g.gap_type.value] = g

    # ── Build mappings ──────────────────────────────────────────────────
    mappings: list[NvidiaTechnologyMappingRecord] = []
    mapping_index = 0

    selected_gap_types = set(gap_result_by_type)
    for gap_type_str, candidate_techs in GAP_TECHNOLOGY_CANDIDATES.items():
        if gap_type_str not in selected_gap_types:
            continue
        gap_result = gap_result_by_type[gap_type_str]
        rag_ctxs = rag_contexts_by_gap.get(gap_type_str, [])
        if not rag_ctxs and gap_result is not None:
            rag_ctxs = rag_contexts_by_gap.get(gap_result.gap_id, [])

        for tech in candidate_techs:
            mapping_index += 1
            mapping_id = f"map-{run_id}-{mapping_index}"

            score_feat, conf_feat = extract_mapping_features(
                gap_type=gap_type_str,
                technology=tech,
                rag_contexts=rag_ctxs,
                evidence_items=evidence_items,
                gap_result=gap_result,
            )

            # Provenance is factual metadata and must survive score/calibration
            # blockers. A blocked decision is not the same as absent evidence.
            rag_ctx_ids: list[str] = []
            for ctx in rag_ctxs:
                cid = ctx.get("context_id") or ctx.get("chunk_id") or ""
                if cid and _context_matches_technology(ctx, tech):
                    rag_ctx_ids.append(str(cid))

            ev_ids: list[str] = []
            gap_support_ids = set(gap_result.supporting_evidence_ids if gap_result else [])
            for item in evidence_items:
                eid = _evidence_id(item)
                if eid and eid in gap_support_ids:
                    ev_ids.append(eid)

            if is_blocked:
                mappings.append(
                    NvidiaTechnologyMappingRecord(
                        mapping_id=mapping_id,
                        gap_type=gap_type_str,
                        nvidia_technology=tech,
                        technology_category=NVIDIA_TECHNOLOGIES.get(tech, ""),
                        required_gap_features=list(score_feat.model_dump().keys()),
                        required_rag_topics=_TECHNOLOGY_TOPIC_KEYWORDS.get(tech, []),
                        required_evidence_types=["fact", "strong_inference"],
                        mapping_score=0.0,
                        mapping_confidence=0.0,
                        uncertainty=1.0,
                        supporting_rag_context_ids=rag_ctx_ids,
                        supporting_evidence_ids=ev_ids,
                        calibration_decision_ids=REQUIRED_MAPPING_DECISIONS,
                        production_allowed=False,
                        blockers=blockers,
                        explanation=f"Mapping '{gap_type_str} → {tech}' blocked: "
                        f"required calibration decisions missing or golden set insufficient.",
                    )
                )
                continue

            assert cal_values is not None

            score_weights = _lookup_weight_dict("nvidia_mapping.mapping_score_weights", cal_values)
            conf_weights = _lookup_weight_dict("nvidia_mapping.mapping_confidence_weights", cal_values)
            production_threshold = _lookup_float("nvidia_mapping.production_threshold", cal_values)
            min_rag = _lookup_int("nvidia_mapping.minimum_rag_contexts", cal_values)
            min_evidence = _lookup_int("nvidia_mapping.minimum_evidence_support", cal_values)
            uncertainty_penalty_mult = _lookup_float("nvidia_mapping.uncertainty_penalty", cal_values)

            invalid_calibration_blockers = []
            if score_weights is None:
                invalid_calibration_blockers.append("Mapping score weights calibration record has invalid type")
            if conf_weights is None:
                invalid_calibration_blockers.append("Mapping confidence weights calibration record has invalid type")
            if production_threshold is None:
                invalid_calibration_blockers.append("Mapping production threshold calibration record is not numeric")
            if min_rag is None:
                invalid_calibration_blockers.append("Minimum RAG contexts calibration record is not numeric")
            if min_evidence is None:
                invalid_calibration_blockers.append("Minimum evidence support calibration record is not numeric")
            if uncertainty_penalty_mult is None:
                invalid_calibration_blockers.append("Uncertainty penalty calibration record is not numeric")

            if invalid_calibration_blockers:
                mappings.append(
                    NvidiaTechnologyMappingRecord(
                        mapping_id=mapping_id,
                        gap_type=gap_type_str,
                        nvidia_technology=tech,
                        technology_category=NVIDIA_TECHNOLOGIES.get(tech, ""),
                        required_gap_features=list(score_feat.model_dump().keys()),
                        required_rag_topics=_TECHNOLOGY_TOPIC_KEYWORDS.get(tech, []),
                        required_evidence_types=["fact", "strong_inference"],
                        mapping_score=0.0,
                        mapping_confidence=0.0,
                        uncertainty=1.0,
                        supporting_rag_context_ids=[],
                        supporting_evidence_ids=[],
                        calibration_decision_ids=REQUIRED_MAPPING_DECISIONS,
                        production_allowed=False,
                        blockers=invalid_calibration_blockers,
                        explanation=f"Mapping '{gap_type_str} → {tech}' blocked: weight dicts invalid.",
                    )
                )
                continue

            # ── Compute mapping_score ───────────────────────────────────
            assert score_weights is not None
            assert conf_weights is not None
            assert production_threshold is not None
            assert min_rag is not None
            assert min_evidence is not None
            assert uncertainty_penalty_mult is not None

            feat_dict = score_feat.model_dump(mode="json")
            raw_score = _compute_weighted_score(feat_dict, score_weights)

            unc_penalty = score_feat.uncertainty_penalty * uncertainty_penalty_mult
            final_score = max(0.0, min(1.0, raw_score - unc_penalty))

            # ── Compute mapping_confidence ──────────────────────────────
            conf_feat_dict = conf_feat.model_dump(mode="json")
            raw_conf = _compute_weighted_score(conf_feat_dict, conf_weights)
            final_conf = max(0.0, min(1.0, raw_conf - unc_penalty))

            # ── Determine status ────────────────────────────────────────
            status: NvidiaMappingStatus
            prod_allowed = True
            mapping_blockers: list[str] = []

            rag_count = len(rag_ctx_ids)
            ev_count = len(ev_ids)

            if rag_count == 0 and ev_count == 0:
                status = NvidiaMappingStatus.NEEDS_MORE_EVIDENCE
                prod_allowed = False
                mapping_blockers.append("No RAG contexts and no evidence items supporting this mapping.")
            elif min_rag is not None and rag_count < min_rag:
                status = NvidiaMappingStatus.NEEDS_MORE_EVIDENCE
                prod_allowed = False
                mapping_blockers.append(f"RAG contexts ({rag_count}) below minimum ({min_rag}).")
            elif min_evidence is not None and ev_count < min_evidence:
                status = NvidiaMappingStatus.NEEDS_MORE_EVIDENCE
                prod_allowed = False
                mapping_blockers.append(f"Evidence items ({ev_count}) below minimum ({min_evidence}).")
            elif production_threshold is not None and final_score < production_threshold:
                status = NvidiaMappingStatus.NEEDS_REVIEW
                prod_allowed = False
                mapping_blockers.append(
                    f"Mapping score ({round(final_score, 4)}) below production threshold ({production_threshold})."
                )
            else:
                status = NvidiaMappingStatus.PASSED

            # ── Build explanation ───────────────────────────────────────
            explanation_parts: list[str] = [
                f"Mapping '{gap_type_str} → {tech}': score={round(final_score, 4)}, confidence={round(final_conf, 4)}",
                f"RAG technology contexts: {rag_count}, Company gap evidence items: {ev_count}",
            ]
            if status == NvidiaMappingStatus.PASSED:
                explanation_parts.append("All checks passed. Production allowed.")
            elif status == NvidiaMappingStatus.NEEDS_MORE_EVIDENCE:
                explanation_parts.append("Insufficient evidence for reliable mapping.")
            elif status == NvidiaMappingStatus.NEEDS_REVIEW:
                explanation_parts.append(f"Score below production threshold ({production_threshold}).")

            mappings.append(
                NvidiaTechnologyMappingRecord(
                    mapping_id=mapping_id,
                    gap_type=gap_type_str,
                    nvidia_technology=tech,
                    technology_category=NVIDIA_TECHNOLOGIES.get(tech, ""),
                    required_gap_features=list(score_feat.model_dump().keys()),
                    required_rag_topics=_TECHNOLOGY_TOPIC_KEYWORDS.get(tech, []),
                    required_evidence_types=["fact", "strong_inference"],
                    mapping_score=round(final_score, 4),
                    mapping_confidence=round(final_conf, 4),
                    uncertainty=round(unc_penalty, 4),
                    supporting_rag_context_ids=rag_ctx_ids,
                    supporting_evidence_ids=ev_ids,
                    calibration_decision_ids=REQUIRED_MAPPING_DECISIONS,
                    production_allowed=prod_allowed,
                    blockers=mapping_blockers,
                    explanation="; ".join(explanation_parts),
                )
            )

    metrics = compute_mapping_metrics(mappings)

    # ── Determine overall status ────────────────────────────────────────
    overall_status: str
    if is_blocked:
        overall_status = NvidiaMappingStatus.BLOCKED_UNCALIBRATED_MAPPING.value
    elif any(m.production_allowed for m in mappings):
        overall_status = NvidiaMappingStatus.PASSED.value
    elif any(m.supporting_rag_context_ids and m.supporting_evidence_ids for m in mappings):
        # At least one candidate is evidence-grounded and RAG-grounded. A score
        # below the calibrated production threshold requires review; unsupported
        # sibling candidates must not downgrade the whole gap to missing evidence.
        overall_status = NvidiaMappingStatus.NEEDS_REVIEW.value
    elif mappings:
        overall_status = NvidiaMappingStatus.NEEDS_MORE_EVIDENCE.value
    else:
        overall_status = NvidiaMappingStatus.FAILED.value

    # ── Compute calibration metrics ─────────────────────────────────────
    cal_metrics = NvidiaMappingCalibrationMetrics(
        evidence_supported_mapping_rate=metrics.evidence_supported_mapping_rate,
        rag_supported_mapping_rate=metrics.rag_supported_mapping_rate,
        unsupported_mapping_rate=(metrics.unsupported_mapping_count / max(1, metrics.total_mapping_count)),
        technology_coverage=(len(metrics.mappings_by_technology) / max(1, len(NVIDIA_TECHNOLOGIES))),
    )

    return {
        "run_id": run_id,
        "nvidia_technology_mappings": [m.model_dump(mode="json") for m in mappings],
        "nvidia_mapping_metrics": metrics.model_dump(mode="json"),
        "nvidia_mapping_calibration_metrics": cal_metrics.model_dump(mode="json"),
        "mapping_status": overall_status,
        "production_allowed": all(m.production_allowed for m in mappings),
        "blockers": blockers,
    }


def compute_mapping_metrics(
    mappings: list[NvidiaTechnologyMappingRecord],
) -> NvidiaMappingMetrics:
    total = len(mappings)
    prod_allowed = sum(1 for m in mappings if m.production_allowed)
    blocked = sum(1 for m in mappings if not m.production_allowed)
    unsupported = sum(1 for m in mappings if not m.supporting_rag_context_ids and not m.supporting_evidence_ids)

    by_gap_type: dict[str, int] = {}
    by_tech: dict[str, int] = {}
    for m in mappings:
        by_gap_type[m.gap_type] = by_gap_type.get(m.gap_type, 0) + 1
        by_tech[m.nvidia_technology] = by_tech.get(m.nvidia_technology, 0) + 1

    scores = [m.mapping_score for m in mappings]
    confs = [m.mapping_confidence for m in mappings]

    rag_supported = sum(1 for m in mappings if m.supporting_rag_context_ids)
    ev_supported = sum(1 for m in mappings if m.supporting_evidence_ids)

    return NvidiaMappingMetrics(
        total_mapping_count=total,
        production_allowed_mapping_count=prod_allowed,
        blocked_mapping_count=blocked,
        mappings_by_gap_type=by_gap_type,
        mappings_by_technology=by_tech,
        average_mapping_score=_mean(scores),
        average_mapping_confidence=_mean(confs),
        unsupported_mapping_count=unsupported,
        missing_calibration_count=len(REQUIRED_MAPPING_DECISIONS),
        rag_supported_mapping_rate=rag_supported / max(1, total),
        evidence_supported_mapping_rate=ev_supported / max(1, total),
    )


__all__ = [
    "NvidiaMappingStatus",
    "NvidiaTechnologyMappingRecord",
    "NvidiaMappingFeatures",
    "NvidiaMappingConfidenceFeatures",
    "NvidiaMappingMetrics",
    "NvidiaMappingCalibrationMetrics",
    "GoldenMappingSample",
    "REQUIRED_MAPPING_DECISIONS",
    "NVIDIA_TECHNOLOGIES",
    "GAP_TECHNOLOGY_CANDIDATES",
    "GOLDEN_MAPPING_SAMPLES",
    "GOLDEN_SET_STATUS",
    "build_nvidia_technology_mappings",
    "compute_mapping_metrics",
    "extract_mapping_features",
]
