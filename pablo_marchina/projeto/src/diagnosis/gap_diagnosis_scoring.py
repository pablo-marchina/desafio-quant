"""Quantitative gap diagnosis — severity and confidence scores with calibration gating.

Produces per-gap-type severity and confidence scores in [0, 1] when all
required calibration decisions are available and calibrated. Blocks otherwise
with ``gap_diagnosis_status="blocked_uncalibrated_gap_diagnosis"``.
"""

from __future__ import annotations

from typing import Any

from src.diagnosis.schemas import (
    ALL_GAP_TYPES,
    GAP_TECH_MAP,
    GapConfidenceFeatures,
    GapDiagnosisFeatures,
    GapDiagnosisMetrics,
    GapDiagnosisResultItem,
    GapDiagnosisStatus,
    GapDiagnosisSummary,
    GapSeverityFeatures,
    GapType,
)
from src.quality.decision_calibration_registry import (
    DecisionCalibrationRecord,
    get_project_decision_inventory,
    validate_decision_for_production,
)

# ── Decision IDs ───────────────────────────────────────────────────────────

SEVERITY_WEIGHTS_DECISION_ID = "gap_diagnosis.severity_weights"
CONFIDENCE_WEIGHTS_DECISION_ID = "gap_diagnosis.confidence_weights"
PRODUCTION_THRESHOLD_DECISION_ID = "gap_diagnosis.production_threshold"
UNCERTAINTY_PENALTY_DECISION_ID = "gap_diagnosis.uncertainty_penalty"
MINIMUM_EVIDENCE_COVERAGE_DECISION_ID = "gap_diagnosis.minimum_evidence_coverage"

REQUIRED_CALIBRATION_DECISIONS: list[str] = [
    SEVERITY_WEIGHTS_DECISION_ID,
    CONFIDENCE_WEIGHTS_DECISION_ID,
    PRODUCTION_THRESHOLD_DECISION_ID,
    UNCERTAINTY_PENALTY_DECISION_ID,
    MINIMUM_EVIDENCE_COVERAGE_DECISION_ID,
]

SEVERITY_FEATURE_NAMES: list[str] = [
    "missing_required_signal_count",
    "weak_evidence_count",
    "rejected_evidence_count",
    "unsupported_claim_count",
    "low_confidence_evidence_count",
    "relevant_signal_absence",
    "nvidia_fit_opportunity_signal_count",
    "implementation_complexity_proxy",
    "business_impact_proxy",
    "uncertainty_penalty",
]

CONFIDENCE_FEATURE_NAMES: list[str] = [
    "supporting_evidence_count",
    "supporting_source_count",
    "average_evidence_confidence",
    "average_source_quality",
    "cross_source_agreement_count",
    "contradiction_count",
    "extraction_success_rate",
    "source_category_coverage",
]


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


# ── Calibration lookup ─────────────────────────────────────────────────────


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


# ── Feature extraction ─────────────────────────────────────────────────────


def _count_by_keyword(
    texts: list[str],
    keywords: list[str],
) -> int:
    count = 0
    for t in texts:
        lower = t.lower()
        for kw in keywords:
            if kw in lower:
                count += 1
                break
    return count


def _text_contains_any(text: str, keywords: list[str]) -> bool:
    lower = text.casefold()
    return any(kw.casefold() in lower for kw in keywords if kw)


def _evidence_text(item: dict[str, Any]) -> str:
    """Return the canonical natural-language evidence payload across schemas."""
    return str(
        item.get("text")
        or item.get("quote_or_evidence")
        or item.get("snippet")
        or item.get("claim")
        or ""
    )


_TECHNICAL_GAP_KEYWORD_ALIASES: dict[str, list[str]] = {
    "external_api_dependency": [
        "external api", "api externa", "third-party api", "api dependency",
        "openai api", "anthropic api", "model api",
    ],
    "high_inference_cost": [
        "inference cost", "custo de inferência", "custo de inferencia",
        "serving cost", "cost per token", "gpu cost",
    ],
    "high_latency": [
        "high latency", "latência", "latencia", "inference speed",
        "real-time inference", "inferência em tempo real", "inferencia em tempo real",
    ],
    "agent_governance_gap": [
        "ai agent", "agente de ia", "agentes de ia", "agentic",
        "guardrail", "governance", "governança", "governanca",
    ],
    "observability_gap": [
        "observability", "observabilidade", "monitoring", "monitoramento",
        "telemetry", "telemetria", "tracing",
    ],
    "model_evaluation_gap": [
        "model evaluation", "avaliação de modelo", "avaliacao de modelo",
        "benchmark", "evaluation framework", "evals",
    ],
    "privacy_or_controlled_deployment_gap": [
        "privacy", "privacidade", "on-premise", "on premises", "on-prem",
        "controlled deployment", "data sovereignty", "soberania de dados",
    ],
    "slow_data_pipeline": [
        "data pipeline", "pipeline de dados", "etl", "data processing",
        "processamento de dados", "stream processing",
    ],
    "heavy_tabular_processing": [
        "tabular", "dados tabulares", "dataframe", "data frame",
        "analytics workload", "carga analítica", "carga analitica",
    ],
    "voice_need": ["voice", "speech", "voz", "audio", "áudio", "transcription"],
    "simulation_need": [
        "simulation", "simulação", "simulacao", "digital twin", "gêmeo digital", "gemeo digital",
    ],
    "computer_vision_need": [
        "computer vision", "visão computacional", "visao computacional",
        "image recognition", "image analysis", "análise de imagem", "analise de imagem",
        "drone imagery", "medical imaging", "diagnóstico por imagem", "diagnostico por imagem",
        "object detection", "plantas daninhas",
    ],
    "robotics_need": ["robotics", "robótica", "robotica", "robot", "autonomous machine"],
    "healthcare_compliance_need": [
        "healthcare", "saúde", "saude", "medical", "medicina", "patient", "paciente",
        "clinical", "clínico", "clinico", "diagnóstico", "diagnostico",
    ],
    "ai_cybersecurity_need": [
        "cybersecurity", "cibersegurança", "ciberseguranca", "threat detection",
        "fraud detection", "security operations",
    ],
}


def _technical_gap_keywords(technical_gaps: list[Any]) -> list[str]:
    keywords: list[str] = []
    for gap in technical_gaps:
        value = str(getattr(gap, "value", gap))
        candidates = [value, value.replace("_", " "), *_TECHNICAL_GAP_KEYWORD_ALIASES.get(value, [])]
        for candidate in candidates:
            normalized = candidate.strip().casefold()
            if normalized and normalized not in keywords:
                keywords.append(normalized)
    return keywords


def _extract_texts_from_items(items: list[dict[str, Any]]) -> list[str]:
    return [text for item in items if (text := _evidence_text(item))]



_GAP_SIGNAL_ALIASES: dict[GapType, tuple[str, ...]] = {
    GapType.COMPUTE_ACCELERATION_GAP: (
        "gpu acceleration", "compute acceleration", "high inference cost",
        "high latency", "throughput bottleneck",
    ),
    GapType.INFERENCE_PERFORMANCE_GAP: (
        "inference latency", "high latency", "low latency", "inference cost",
        "inference performance", "real time inference", "real-time inference",
        "model serving",
    ),
    GapType.TRAINING_SCALABILITY_GAP: (
        "training scalability", "distributed training", "training cost",
        "model training", "fine tuning", "fine-tuning",
    ),
    GapType.MLOPS_DEPLOYMENT_GAP: (
        "mlops", "model deployment", "model serving", "observability",
        "production monitoring", "agent governance",
    ),
    GapType.DATA_PIPELINE_GAP: (
        "data pipeline", "slow data pipeline", "etl", "big data",
        "data processing", "data engineering",
    ),
    GapType.MODEL_OPTIMIZATION_GAP: (
        "model optimization", "inference optimization", "quantization",
        "pruning", "distillation", "model compression",
    ),
    GapType.COMPUTER_VISION_GAP: (
        "computer vision", "visao computacional", "visual inspection",
        "inspecao visual", "image recognition", "object detection",
        "video analytics", "image analytics", "optical character recognition",
    ),
    GapType.GENAI_LLM_GAP: (
        "large language model", "llm", "generative ai", "ia generativa",
        "retrieval augmented generation", "conversational ai", "chatbot",
        "external api dependency",
    ),
    GapType.CYBERSECURITY_AI_GAP: (
        "cybersecurity", "ciberseguranca", "threat detection",
        "security operations", "network anomaly", "malware detection",
    ),
    GapType.NVIDIA_ECOSYSTEM_FIT_GAP: (
        "nvidia ecosystem", "nvidia", "cuda", "gpu acceleration", "gpu computing",
    ),
    GapType.EVIDENCE_COVERAGE_GAP: (
        "insufficient evidence", "missing evidence", "evidence coverage",
    ),
    GapType.TECHNICAL_DEPTH_GAP: (
        "technical architecture", "technical stack", "deployment architecture",
        "model architecture", "infrastructure architecture",
    ),
}


def _gap_signal_keywords(gap_type: GapType) -> list[str]:
    keywords = list(_GAP_SIGNAL_ALIASES.get(gap_type, ()))
    keywords.extend(item.value.replace("_", " ") for item in GAP_TECH_MAP.get(gap_type, []))
    return list(dict.fromkeys(keyword.casefold() for keyword in keywords if keyword))


def _evidence_item_text(item: dict[str, Any]) -> str:
    return str(
        item.get("text")
        or item.get("snippet")
        or item.get("claim")
        or item.get("quote_or_evidence")
        or ""
    )


def _matching_evidence_items(
    evidence_items: list[dict[str, Any]],
    gap_type: GapType,
) -> list[dict[str, Any]]:
    keywords = _gap_signal_keywords(gap_type)
    if not keywords:
        return []
    return [item for item in evidence_items if _text_contains_any(_evidence_item_text(item), keywords)]


def _numeric_evidence_confidence(item: dict[str, Any]) -> float:
    for key in ("evidence_confidence_score", "extraction_confidence", "confidence_score"):
        value = item.get(key)
        if isinstance(value, (int, float)):
            return max(0.0, min(1.0, float(value)))
    value = item.get("confidence")
    if isinstance(value, str):
        return {"high": 1.0, "medium": 0.6, "low": 0.3}.get(value.casefold(), 0.0)
    return 0.0


def _compute_uncertainty(
    evidence_count: int,
    avg_confidence: float,
    min_expected: int = 3,
) -> float:
    if evidence_count == 0:
        return 1.0
    coverage_factor = 1.0 - min(1.0, evidence_count / min_expected)
    confidence_factor = 1.0 - avg_confidence
    raw = coverage_factor * 0.6 + confidence_factor * 0.4
    return min(1.0, raw)


def extract_gap_severity_features(
    gap_type: GapType,
    evidence_items: list[dict[str, Any]],
    accepted_evidence_items: list[dict[str, Any]],
    rejected_evidence_items: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    evidence_validation: dict[str, Any] | None,
    collection_metrics: dict[str, Any] | None,
) -> GapSeverityFeatures:
    ev_texts = _extract_texts_from_items(evidence_items)
    ac_texts = _extract_texts_from_items(accepted_evidence_items)
    _extract_texts_from_items(rejected_evidence_items)
    claim_texts = [str(c.get("claim_text", "")) for c in claims if isinstance(c, dict)]
    all_texts = ev_texts + ac_texts + claim_texts

    related_tech_gaps = GAP_TECH_MAP.get(gap_type, [])
    related_keywords = _technical_gap_keywords(related_tech_gaps)

    missing_required_signal_count = 0
    for kw in related_keywords:
        if not _text_contains_any(" ".join(all_texts), [kw]):
            missing_required_signal_count += 1

    weak_evidence_count = sum(
        1 for item in matching_items if _numeric_evidence_confidence(item) < 0.4
    )

    rejected_evidence_count = len(rejected_evidence_items)

    unsupported_claim_count = sum(1 for c in claims if isinstance(c, dict) and c.get("support_status") == "unsupported")

    low_confidence_evidence_count = sum(
        1 for item in evidence_items if isinstance(item.get("confidence"), str) and item["confidence"] in ("low",)
    )

    relevant_signal_absence = 0.0 if has_relevant_signal else 1.0

    nvidia_fit_keywords = [
        "gpu",
        "cuda",
        "tensorrt",
        "nvidia",
        "triton",
        "rapids",
        "cudf",
        "cuml",
    ]
    nvidia_fit_opportunity_signal_count = _count_by_keyword(all_texts, nvidia_fit_keywords)

    nvidia_signal_count = _count_by_keyword(all_texts, ["nvidia", "cuda", "gpu"])
    implementation_complexity_proxy = min(1.0, 0.3 + nvidia_signal_count * 0.1)

    ai_signal_count = _count_by_keyword(
        all_texts,
        ["machine learning", "deep learning", "ai", "inteligencia"],
    )
    business_impact_proxy = min(1.0, ai_signal_count * 0.15)

    matching_confidences = [_numeric_evidence_confidence(item) for item in matching_items]
    uncertainty_penalty = _compute_uncertainty(
        evidence_count=len(matching_items),
        avg_confidence=_mean(matching_confidences),
        min_expected=1,
    )

    # Normalize count-based features to [0, 1] so weighted scoring stays in range
    _MAX_MISSING_SIGNALS = 12.0
    _MAX_WEAK_EVIDENCE = 10.0
    _MAX_REJECTED = 5.0
    _MAX_UNSUPPORTED = 5.0
    _MAX_LOW_CONFIDENCE = 10.0
    _MAX_NVIDIA_OPPORTUNITY = 6.0

    return GapSeverityFeatures(
        missing_required_signal_count=round(min(1.0, missing_required_signal_count / _MAX_MISSING_SIGNALS), 4),
        weak_evidence_count=round(min(1.0, weak_evidence_count / _MAX_WEAK_EVIDENCE), 4),
        rejected_evidence_count=round(min(1.0, rejected_evidence_count / _MAX_REJECTED), 4),
        unsupported_claim_count=round(min(1.0, unsupported_claim_count / _MAX_UNSUPPORTED), 4),
        low_confidence_evidence_count=round(min(1.0, low_confidence_evidence_count / _MAX_LOW_CONFIDENCE), 4),
        relevant_signal_absence=round(relevant_signal_absence, 4),
        nvidia_fit_opportunity_signal_count=round(
            min(1.0, nvidia_fit_opportunity_signal_count / _MAX_NVIDIA_OPPORTUNITY), 4
        ),
        implementation_complexity_proxy=round(implementation_complexity_proxy, 4),
        business_impact_proxy=round(business_impact_proxy, 4),
        uncertainty_penalty=round(uncertainty_penalty, 4),
    )


def extract_gap_confidence_features(
    gap_type: GapType,
    evidence_items: list[dict[str, Any]],
    accepted_evidence_items: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    collection_metrics: dict[str, Any] | None,
    extraction_metrics: dict[str, Any] | None,
) -> GapConfidenceFeatures:
    ev_texts = _extract_texts_from_items(evidence_items)
    ac_texts = _extract_texts_from_items(accepted_evidence_items)
    claim_texts = [str(c.get("claim_text", "")) for c in claims if isinstance(c, dict)]
    ev_texts + ac_texts + claim_texts

    related_tech_gaps = GAP_TECH_MAP.get(gap_type, [])
    related_keywords = _technical_gap_keywords(related_tech_gaps)

    supporting_evidence_count = 0
    if related_keywords:
        for item in evidence_items:
            text = _evidence_text(item)
            if _text_contains_any(text, related_keywords):
                supporting_evidence_count += 1

    source_ids: set[str] = set()
    for item in evidence_items:
        sid = item.get("source_url") or item.get("url") or item.get("source_id") or ""
        if sid:
            source_ids.add(str(sid))
    supporting_source_count = len(source_ids)

    confidences: list[float] = []
    for item in matching_items:
        confidences.append(_numeric_evidence_confidence(item))
    average_evidence_confidence = _mean(confidences)

    qualities: list[float] = []
    for item in matching_items:
        sq = item.get("source_quality_score")
        if isinstance(sq, (int, float)):
            qualities.append(float(sq))
        elif item.get("source_type") == "official_site":
            qualities.append(1.0)
    average_source_quality = _mean(qualities)

    cross_source_agreement_count = 0
    source_claims: dict[str, set[str]] = {}
    for item in evidence_items:
        sid = item.get("source_url") or item.get("url") or item.get("source_id") or ""
        claim = _evidence_text(item)
        if sid and claim:
            if sid not in source_claims:
                source_claims[sid] = set()
            source_claims[sid].add(claim)
    source_ids_list = list(source_claims.keys())
    for i in range(len(source_ids_list)):
        for j in range(i + 1, len(source_ids_list)):
            if source_claims[source_ids_list[i]] & source_claims[source_ids_list[j]]:
                cross_source_agreement_count += 1

    contradiction_count = sum(1 for c in claims if isinstance(c, dict) and c.get("support_status") == "contradicted")

    extraction_success_rate = 1.0
    if extraction_metrics:
        total = extraction_metrics.get("total_extractions", 0)
        failed = extraction_metrics.get("failed_extractions", 0)
        if total and total > 0:
            extraction_success_rate = 1.0 - (failed / total)

    source_category_coverage = 0.0
    if collection_metrics:
        categories = collection_metrics.get("source_categories_covered")
        if isinstance(categories, list) and categories:
            observed_count = len(categories)
        else:
            observed_count = int(collection_metrics.get("source_category_count", 0) or 0)
        minimums = collection_metrics.get("minimums", {})
        expected = collection_metrics.get("expected_categories")
        if not isinstance(expected, int | float) or expected <= 0:
            expected = (minimums.get("source_category_count", 2) if isinstance(minimums, dict) else 2)
        if expected and expected > 0:
            source_category_coverage = min(1.0, observed_count / float(expected))

    # Normalize count-based features to [0, 1]
    _MAX_SUPPORTING_EVIDENCE = 15.0
    _MAX_SUPPORTING_SOURCES = 8.0
    _MAX_CROSS_AGREEMENT = 6.0
    _MAX_CONTRADICTIONS = 4.0

    return GapConfidenceFeatures(
        supporting_evidence_count=round(min(1.0, supporting_evidence_count), 4),
        supporting_source_count=round(min(1.0, supporting_source_count / _MAX_SUPPORTING_SOURCES), 4),
        average_evidence_confidence=round(average_evidence_confidence, 4),
        average_source_quality=round(average_source_quality, 4),
        cross_source_agreement_count=round(min(1.0, cross_source_agreement_count / _MAX_CROSS_AGREEMENT), 4),
        contradiction_count=round(min(1.0, contradiction_count / _MAX_CONTRADICTIONS), 4),
        extraction_success_rate=round(extraction_success_rate, 4),
        source_category_coverage=round(source_category_coverage, 4),
    )


# ── Weighted score computation ─────────────────────────────────────────────


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


# ── Gap Diagnosis per gap type ─────────────────────────────────────────────


def _diagnose_single_gap(
    gap_type: GapType,
    gap_index: int,
    severity_features: GapSeverityFeatures,
    confidence_features: GapConfidenceFeatures,
    cal_values: dict[str, Any] | None,
    is_blocked: bool,
    blockers: list[str],
    evidence_items: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    accepted_evidence_items: list[dict[str, Any]],
) -> GapDiagnosisResultItem:
    gap_id = f"gap-{gap_index}-{gap_type.value}"

    feat_dict_sev = severity_features.model_dump(mode="json")
    feat_dict_conf = confidence_features.model_dump(mode="json")

    if is_blocked:
        return GapDiagnosisResultItem(
            gap_id=gap_id,
            gap_type=gap_type,
            severity_score=0.0,
            confidence_score=0.0,
            uncertainty=1.0,
            status=GapDiagnosisStatus.BLOCKED_UNCALIBRATED_GAP_DIAGNOSIS,
            features=GapDiagnosisFeatures(severity=severity_features, confidence=confidence_features),
            weights={},
            thresholds={},
            calibration_decision_ids=REQUIRED_CALIBRATION_DECISIONS,
            production_allowed=False,
            blockers=blockers,
            explanation=f"Gap '{gap_type.value}' blocked: required calibration decisions missing or uncalibrated.",
            recommended_investigation="Complete calibration of gap diagnosis decisions before proceeding.",
        )

    assert cal_values is not None  # guaranteed by is_blocked check above
    severity_weights = _lookup_weight_dict(SEVERITY_WEIGHTS_DECISION_ID, cal_values)
    confidence_weights = _lookup_weight_dict(CONFIDENCE_WEIGHTS_DECISION_ID, cal_values)
    production_threshold = _lookup_float(PRODUCTION_THRESHOLD_DECISION_ID, cal_values)
    uncertainty_penalty_mult = _lookup_float(UNCERTAINTY_PENALTY_DECISION_ID, cal_values)
    min_evidence_coverage = _lookup_float(MINIMUM_EVIDENCE_COVERAGE_DECISION_ID, cal_values)

    if severity_weights is None:
        return GapDiagnosisResultItem(
            gap_id=gap_id,
            gap_type=gap_type,
            severity_score=0.0,
            confidence_score=0.0,
            uncertainty=1.0,
            status=GapDiagnosisStatus.BLOCKED_UNCALIBRATED_GAP_DIAGNOSIS,
            features=GapDiagnosisFeatures(severity=severity_features, confidence=confidence_features),
            weights={},
            thresholds={},
            calibration_decision_ids=REQUIRED_CALIBRATION_DECISIONS,
            production_allowed=False,
            blockers=blockers + [f"Decision '{SEVERITY_WEIGHTS_DECISION_ID}' current_value is not a dict"],
            explanation=f"Gap '{gap_type.value}' blocked: severity weights decision has invalid type.",
            recommended_investigation="Fix severity_weights calibration record with a valid dict of feature weights.",
        )

    if confidence_weights is None:
        return GapDiagnosisResultItem(
            gap_id=gap_id,
            gap_type=gap_type,
            severity_score=0.0,
            confidence_score=0.0,
            uncertainty=1.0,
            status=GapDiagnosisStatus.BLOCKED_UNCALIBRATED_GAP_DIAGNOSIS,
            features=GapDiagnosisFeatures(severity=severity_features, confidence=confidence_features),
            weights={},
            thresholds={},
            calibration_decision_ids=REQUIRED_CALIBRATION_DECISIONS,
            production_allowed=False,
            blockers=blockers + [f"Decision '{CONFIDENCE_WEIGHTS_DECISION_ID}' current_value is not a dict"],
            explanation=f"Gap '{gap_type.value}' blocked: confidence weights decision has invalid type.",
            recommended_investigation="Fix confidence_weights calibration record with a valid dict of feature weights.",
        )

    raw_severity = _compute_weighted_score(feat_dict_sev, severity_weights)
    raw_confidence = _compute_weighted_score(feat_dict_conf, confidence_weights)

    uncertainty_penalty_value = severity_features.uncertainty_penalty * (uncertainty_penalty_mult or 0.1)
    final_severity = max(0.0, min(1.0, raw_severity + uncertainty_penalty_value))
    final_confidence = max(0.0, min(1.0, raw_confidence - uncertainty_penalty_value))

    thresholds: dict[str, float] = {}
    if production_threshold is not None:
        thresholds["production_threshold"] = production_threshold
    if min_evidence_coverage is not None:
        thresholds["min_evidence_coverage"] = min_evidence_coverage

    status: GapDiagnosisStatus
    prod_allowed = True
    gap_blockers: list[str] = []

    related_keywords = _technical_gap_keywords(GAP_TECH_MAP.get(gap_type, []))
    supporting_evidence_count_raw = sum(
        1
        for item in evidence_items
        if _text_contains_any(
            _evidence_text(item),
            related_keywords,
        )
    ) if related_keywords else 0
    observed_evidence_coverage = (
        supporting_evidence_count_raw / len(evidence_items) if evidence_items else 0.0
    )
    # Absence of a public mention is not evidence that an operational gap
    # exists. Three independent sources can corroborate a positive signal, but
    # they cannot turn silence about latency, cost, governance, or MLOps into a
    # factual diagnosis. Keep the field for audit compatibility and force it off.
    corroborated_absence = False
    thresholds["observed_evidence_coverage"] = round(observed_evidence_coverage, 4)
    thresholds["corroborated_absence"] = 1.0 if corroborated_absence else 0.0

    if len(evidence_items) == 0:
        status = GapDiagnosisStatus.NEEDS_MORE_EVIDENCE
        prod_allowed = False
        gap_blockers.append("No evidence items available for gap diagnosis")
    elif (
        min_evidence_coverage is not None
        and observed_evidence_coverage < min_evidence_coverage
        and not corroborated_absence
    ):
        status = GapDiagnosisStatus.NEEDS_MORE_EVIDENCE
        prod_allowed = False
        gap_blockers.append(
            f"Observed positive gap-specific evidence coverage ({observed_evidence_coverage:.4f}) "
            f"below minimum ({min_evidence_coverage:.4f}); public silence is not "
            "accepted as proof of an operational gap"
        )
    elif production_threshold is not None and final_severity > production_threshold:
        # Crossing the calibrated severity threshold means a gap was detected;
        # it is not a failure of the diagnosis process. Keep it retrieval-eligible
        # and explicitly mark it for review by downstream decision makers.
        status = GapDiagnosisStatus.NEEDS_REVIEW
    else:
        status = GapDiagnosisStatus.PASSED

    supporting_ids: list[str] = []
    for item in evidence_items:
        if not related_keywords or not _text_contains_any(_evidence_text(item), related_keywords):
            continue
        eid = item.get("id") or item.get("evidence_id") or ""
        if eid:
            supporting_ids.append(str(eid))

    claim_ids: list[str] = []
    for c in claims:
        cid = c.get("id") or c.get("claim_id") or ""
        if cid:
            claim_ids.append(str(cid))

    explanation_parts: list[str] = [
        f"Gap '{gap_type.value}': severity={round(final_severity, 4)}, confidence={round(final_confidence, 4)}",
        f"Severity features: {severity_features.model_dump(mode='json')}",
        f"Confidence features: {confidence_features.model_dump(mode='json')}",
    ]
    if status == GapDiagnosisStatus.PASSED:
        explanation_parts.append("No decision-threshold gap was detected from the available evidence.")
    elif status == GapDiagnosisStatus.NEEDS_REVIEW:
        explanation_parts.append(
            f"Evidence-supported gap exceeds the calibrated severity threshold ({production_threshold}) and requires review."
        )
    elif status == GapDiagnosisStatus.FAILED:
        explanation_parts.append("The diagnosis process failed a validity gate.")
    elif status == GapDiagnosisStatus.NEEDS_MORE_EVIDENCE:
        explanation_parts.append("Insufficient positive evidence for reliable diagnosis.")

    return GapDiagnosisResultItem(
        gap_id=gap_id,
        gap_type=gap_type,
        severity_score=round(final_severity, 4),
        confidence_score=round(final_confidence, 4),
        uncertainty=round(uncertainty_penalty_value, 4),
        status=status,
        features=GapDiagnosisFeatures(severity=severity_features, confidence=confidence_features),
        weights={
            "severity_weights": dict(severity_weights),
            "confidence_weights": dict(confidence_weights),
        },
        thresholds=thresholds,
        supporting_evidence_ids=supporting_ids,
        related_claim_ids=claim_ids,
        calibration_decision_ids=REQUIRED_CALIBRATION_DECISIONS,
        production_allowed=prod_allowed,
        blockers=gap_blockers,
        explanation="; ".join(explanation_parts),
        recommended_investigation=(
            "Collect additional positive evidence for this gap area."
            if status == GapDiagnosisStatus.NEEDS_MORE_EVIDENCE
            else (
                "Review the supporting company evidence and retrieve NVIDIA technical context."
                if status == GapDiagnosisStatus.NEEDS_REVIEW
                else "No further investigation required at this time."
            )
        ),
    )


# ── Main entry point ───────────────────────────────────────────────────────


def diagnose_gaps_quantitative(
    run_id: str,
    startup_id: str | None = None,
    startup_profile: dict[str, Any] | None = None,
    evidence_items: list[dict[str, Any]] | None = None,
    accepted_evidence_items: list[dict[str, Any]] | None = None,
    rejected_evidence_items: list[dict[str, Any]] | None = None,
    claims: list[dict[str, Any]] | None = None,
    evidence_validation: dict[str, Any] | None = None,
    ai_native_score: float | None = None,
    nvidia_fit_score: float | None = None,
    scoring_metrics: dict[str, Any] | None = None,
    collection_metrics: dict[str, Any] | None = None,
    extraction_metrics: dict[str, Any] | None = None,
    inventory: list[DecisionCalibrationRecord] | None = None,
) -> GapDiagnosisSummary:
    if inventory is None:
        inventory = get_project_decision_inventory()

    evidence_items = evidence_items or []
    accepted_evidence_items = accepted_evidence_items or []
    rejected_evidence_items = rejected_evidence_items or []
    claims = claims or []

    # ── Calibration gate ────────────────────────────────────────────────
    cal_values, cal_ok, blockers = _lookup_calibration_group(REQUIRED_CALIBRATION_DECISIONS, inventory=inventory)

    is_blocked = not cal_ok

    # ── Unsupported critical claims check ───────────────────────────────
    unsupported_critical_count = sum(
        1
        for c in claims
        if isinstance(c, dict) and c.get("support_status") == "unsupported" and c.get("is_critical", False)
    )
    if unsupported_critical_count > 0:
        return GapDiagnosisSummary(
            run_id=run_id,
            gap_diagnosis_status=GapDiagnosisStatus.FAILED,
            gaps=[],
            metrics=GapDiagnosisMetrics(
                total_gap_count=0,
                production_allowed_gap_count=0,
                blocked_gap_count=0,
                average_gap_severity=0.0,
                average_gap_confidence=0.0,
                high_severity_gap_count=0,
                evidence_coverage_gap_count=0,
                missing_calibration_count=(len(REQUIRED_CALIBRATION_DECISIONS) if is_blocked else 0),
                calibrated_decision_count=(0 if is_blocked else len(REQUIRED_CALIBRATION_DECISIONS)),
                gap_uncertainty_mean=0.0,
            ),
            calibration_status="uncalibrated" if is_blocked else "calibrated",
            production_allowed=False,
            blockers=[f"Unsupported critical claims count: {unsupported_critical_count} > 0"],
        )

    # ── Diagnose each gap type ──────────────────────────────────────────
    gap_results: list[GapDiagnosisResultItem] = []

    for i, gap_type in enumerate(ALL_GAP_TYPES):
        sev_features = extract_gap_severity_features(
            gap_type=gap_type,
            evidence_items=evidence_items,
            accepted_evidence_items=accepted_evidence_items,
            rejected_evidence_items=rejected_evidence_items,
            claims=claims,
            evidence_validation=evidence_validation,
            collection_metrics=collection_metrics,
        )
        conf_features = extract_gap_confidence_features(
            gap_type=gap_type,
            evidence_items=evidence_items,
            accepted_evidence_items=accepted_evidence_items,
            claims=claims,
            collection_metrics=collection_metrics,
            extraction_metrics=extraction_metrics,
        )

        result = _diagnose_single_gap(
            gap_type=gap_type,
            gap_index=i,
            severity_features=sev_features,
            confidence_features=conf_features,
            cal_values=cal_values,
            is_blocked=is_blocked,
            blockers=blockers,
            evidence_items=evidence_items,
            claims=claims,
            accepted_evidence_items=accepted_evidence_items,
        )
        gap_results.append(result)

    # ── Compute metrics ─────────────────────────────────────────────────
    total = len(gap_results)
    prod_allowed_count = sum(1 for g in gap_results if g.production_allowed)
    blocked_count = sum(1 for g in gap_results if not g.production_allowed)
    avg_severity = _mean([g.severity_score for g in gap_results])
    avg_confidence = _mean([g.confidence_score for g in gap_results])
    high_severity_count = 0
    evidence_coverage_count = sum(1 for g in gap_results if g.gap_type == GapType.EVIDENCE_COVERAGE_GAP)
    missing_cal = len(REQUIRED_CALIBRATION_DECISIONS) if is_blocked else 0
    cal_count = 0 if is_blocked else len(REQUIRED_CALIBRATION_DECISIONS)
    uncertainty_mean = _mean([g.uncertainty for g in gap_results])

    metrics = GapDiagnosisMetrics(
        total_gap_count=total,
        production_allowed_gap_count=prod_allowed_count,
        blocked_gap_count=blocked_count,
        average_gap_severity=round(avg_severity, 4),
        average_gap_confidence=round(avg_confidence, 4),
        high_severity_gap_count=high_severity_count,
        evidence_coverage_gap_count=evidence_coverage_count,
        missing_calibration_count=missing_cal,
        calibrated_decision_count=cal_count,
        gap_uncertainty_mean=round(uncertainty_mean, 4),
    )

    # ── Determine overall status ────────────────────────────────────────
    overall_status: GapDiagnosisStatus
    if is_blocked:
        overall_status = GapDiagnosisStatus.BLOCKED_UNCALIBRATED_GAP_DIAGNOSIS
    elif any(g.status == GapDiagnosisStatus.FAILED for g in gap_results):
        overall_status = GapDiagnosisStatus.FAILED
    elif any(g.status == GapDiagnosisStatus.NEEDS_MORE_EVIDENCE for g in gap_results):
        overall_status = GapDiagnosisStatus.NEEDS_REVIEW
    else:
        overall_status = GapDiagnosisStatus.PASSED

    prod_allowed = (
        not is_blocked
        and all(g.production_allowed for g in gap_results)
        and overall_status not in (GapDiagnosisStatus.FAILED, GapDiagnosisStatus.NEEDS_MORE_EVIDENCE)
    )

    return GapDiagnosisSummary(
        run_id=run_id,
        gap_diagnosis_status=overall_status,
        gaps=gap_results,
        metrics=metrics,
        calibration_status="uncalibrated" if is_blocked else "calibrated",
        production_allowed=prod_allowed,
        blockers=blockers,
    )


__all__ = [
    "SEVERITY_WEIGHTS_DECISION_ID",
    "CONFIDENCE_WEIGHTS_DECISION_ID",
    "PRODUCTION_THRESHOLD_DECISION_ID",
    "UNCERTAINTY_PENALTY_DECISION_ID",
    "MINIMUM_EVIDENCE_COVERAGE_DECISION_ID",
    "REQUIRED_CALIBRATION_DECISIONS",
    "GapDiagnosisStatus",
    "diagnose_gaps_quantitative",
    "extract_gap_severity_features",
    "extract_gap_confidence_features",
]
