from __future__ import annotations

from src.diagnosis.gap_diagnosis_scoring import extract_gap_confidence_features
from src.diagnosis.schemas import (
    GapConfidenceFeatures,
    GapDiagnosisFeatures,
    GapDiagnosisResultItem,
    GapDiagnosisStatus,
    GapSeverityFeatures,
    GapType,
)
import src.recommendation.nvidia_technology_mapping as mapping_module


def _features() -> GapDiagnosisFeatures:
    return GapDiagnosisFeatures(
        severity=GapSeverityFeatures(
            missing_required_signal_count=0.0,
            weak_evidence_count=0.0,
            rejected_evidence_count=0.0,
            unsupported_claim_count=0.0,
            low_confidence_evidence_count=0.0,
            relevant_signal_absence=0.0,
            nvidia_fit_opportunity_signal_count=0.5,
            implementation_complexity_proxy=0.5,
            business_impact_proxy=0.5,
            uncertainty_penalty=0.0,
        ),
        confidence=GapConfidenceFeatures(
            supporting_evidence_count=1.0,
            supporting_source_count=1.0,
            average_evidence_confidence=0.95,
            average_source_quality=1.0,
            cross_source_agreement_count=0.0,
            contradiction_count=0.0,
            extraction_success_rate=1.0,
            source_category_coverage=1.0,
        ),
    )


def _gap(gap_type: GapType, evidence_ids: list[str]) -> GapDiagnosisResultItem:
    return GapDiagnosisResultItem(
        gap_id=f"gap-{gap_type.value}",
        gap_type=gap_type,
        severity_score=0.65,
        confidence_score=0.9,
        uncertainty=0.05,
        status=GapDiagnosisStatus.PASSED,
        features=_features(),
        weights={},
        thresholds={},
        supporting_evidence_ids=evidence_ids,
        production_allowed=True,
    )


def test_natural_computer_vision_phrase_supports_only_cv_gap() -> None:
    evidence = [{
        "evidence_id": "ev-cv",
        "text": "Industrial computer vision and visual inspection for manufacturing plants.",
        "source_id": "official",
        "source_url": "https://example.com/product",
        "source_type": "official_site",
        "extraction_confidence": 0.95,
        "source_quality_score": 1.0,
    }]
    cv = extract_gap_confidence_features(GapType.COMPUTER_VISION_GAP, evidence, evidence, [], {}, {})
    llm = extract_gap_confidence_features(GapType.GENAI_LLM_GAP, evidence, evidence, [], {}, {})
    assert cv.supporting_evidence_count == 1.0
    assert cv.average_evidence_confidence == 0.95
    assert llm.supporting_evidence_count == 0.0


def test_mapping_uses_gap_evidence_and_rag_context_for_distinct_claims(monkeypatch) -> None:
    evidence = [{
        "evidence_id": "ev-cv",
        "text": "Industrial computer vision and visual inspection for manufacturing plants.",
        "source_id": "official",
        "source_url": "https://example.com/product",
        "source_type": "official_site",
        "extraction_confidence": 0.95,
        "source_quality_score": 1.0,
    }]
    context = {
        "context_id": "ctx-tensorrt",
        "chunk_id": "ctx-tensorrt",
        "product": "TensorRT",
        "title": "TensorRT inference optimization",
        "content": "TensorRT optimizes deep-learning inference for computer vision workloads.",
        "source_id": "nvidia-tensorrt",
        "url": "https://docs.nvidia.com/deeplearning/tensorrt/",
        "relevance_score": 0.95,
        "citation_ready": True,
    }
    values = {
        "nvidia_mapping.mapping_score_weights": {
            "gap_severity_score": 1.0,
            "gap_confidence_score": 1.0,
            "rag_context_count_for_technology": 1.0,
            "rag_relevance_mean_for_technology": 1.0,
            "evidence_support_count": 1.0,
            "evidence_confidence_mean": 1.0,
            "source_quality_mean": 1.0,
            "technology_topic_match_count": 1.0,
            "startup_profile_signal_match_count": 0.0,
            "uncertainty_penalty": 0.0,
        },
        "nvidia_mapping.mapping_confidence_weights": {
            "supporting_rag_context_count": 1.0,
            "supporting_evidence_count": 1.0,
            "average_rag_relevance_score": 1.0,
            "average_evidence_confidence_score": 1.0,
            "cross_source_support_count": 1.0,
            "contradiction_count": 0.0,
            "corpus_payload_completeness_rate": 1.0,
        },
        "nvidia_mapping.production_threshold": 0.0,
        "nvidia_mapping.minimum_rag_contexts": 1,
        "nvidia_mapping.minimum_evidence_support": 1,
        "nvidia_mapping.uncertainty_penalty": 0.0,
        "nvidia_mapping.technology_priority_policy": {},
    }
    monkeypatch.setattr(mapping_module, "_lookup_calibration_group", lambda *args, **kwargs: (values, True, []))
    result = mapping_module.build_nvidia_technology_mappings(
        run_id="run-1",
        rag_contexts_by_gap={"computer_vision_gap": [context]},
        gap_results=[
            _gap(GapType.COMPUTER_VISION_GAP, ["ev-cv"]),
            _gap(GapType.GENAI_LLM_GAP, []),
        ],
        gap_metrics=None,
        evidence_items=evidence,
        inventory=[],
    )
    mappings = result["nvidia_technology_mappings"]
    assert mappings
    assert {item["gap_type"] for item in mappings} == {"computer_vision_gap"}
    tensorrt = next(item for item in mappings if item["nvidia_technology"] == "TensorRT")
    assert tensorrt["production_allowed"] is True
    assert tensorrt["supporting_evidence_ids"] == ["ev-cv"]
    assert tensorrt["supporting_rag_context_ids"] == ["ctx-tensorrt"]
    assert "TensorRT" not in evidence[0]["text"]
