"""Deterministic evidence validation package."""

from src.validation.evidence_validator import (
    EvidenceKind,
    ValidatedEvidence,
    flag_unsourced_claims,
    validate_evidence,
    validate_evidence_batch,
)

__all__ = [
    "EvidenceKind",
    "ValidatedEvidence",
    "validate_evidence",
    "validate_evidence_batch",
    "flag_unsourced_claims",
]
