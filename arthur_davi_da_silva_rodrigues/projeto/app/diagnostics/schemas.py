from dataclasses import dataclass


@dataclass(frozen=True)
class GapDiagnosis:
    gap_type: str
    priority: str
    confidence: float
    evidence_basis: str
    rationale: str
    suggested_action: str


@dataclass(frozen=True)
class GapDiagnosisReport:
    gaps: tuple[GapDiagnosis, ...]
    summary: str
