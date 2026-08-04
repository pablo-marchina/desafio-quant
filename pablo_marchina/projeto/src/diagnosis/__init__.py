"""Gap Diagnosis + NVIDIA Mapping package.

Deterministic detection of production AI gaps and mapping to NVIDIA technologies.
"""

from src.diagnosis.gap_diagnosis import diagnose_gaps
from src.diagnosis.gap_diagnosis_scoring import (
    REQUIRED_CALIBRATION_DECISIONS,
    GapDiagnosisStatus,
    diagnose_gaps_quantitative,
    extract_gap_confidence_features,
    extract_gap_severity_features,
)
from src.diagnosis.nvidia_mapping import build_technology_candidates, map_gap_to_technologies
from src.diagnosis.schemas import (
    ALL_GAP_TYPES,
    GAP_TECH_MAP,
    EvidenceTag,
    GapConfidenceFeatures,
    GapDiagnosisFeatures,
    GapDiagnosisMetrics,
    GapDiagnosisResult,
    GapDiagnosisResultItem,
    GapDiagnosisSummary,
    GapSeverityFeatures,
    GapType,
    GapWithEvidence,
    NvidiaTechnologyCandidate,
)

__all__ = [
    "ALL_GAP_TYPES",
    "GAP_TECH_MAP",
    "EvidenceTag",
    "GapConfidenceFeatures",
    "GapDiagnosisFeatures",
    "GapDiagnosisMetrics",
    "GapDiagnosisResult",
    "GapDiagnosisResultItem",
    "GapDiagnosisStatus",
    "GapDiagnosisSummary",
    "GapSeverityFeatures",
    "GapType",
    "GapWithEvidence",
    "NvidiaTechnologyCandidate",
    "REQUIRED_CALIBRATION_DECISIONS",
    "build_technology_candidates",
    "diagnose_gaps",
    "diagnose_gaps_quantitative",
    "extract_gap_confidence_features",
    "extract_gap_severity_features",
    "map_gap_to_technologies",
]
