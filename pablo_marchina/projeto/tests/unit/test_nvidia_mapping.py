"""Tests for NVIDIA Technology Mapping — coverage, determinism, deduplication."""

from __future__ import annotations

from src.diagnosis.nvidia_mapping import (
    _TECH_MATRIX,
    build_technology_candidates,
    map_gap_to_technologies,
)
from src.diagnosis.schemas import EvidenceTag, GapWithEvidence, NvidiaTechnologyCandidate
from src.extraction.schemas import ConfidenceLevel, TechnicalGap


class TestMapGapToTechnologies:
    def test_known_gap_returns_candidates(self) -> None:
        candidates = map_gap_to_technologies(TechnicalGap.HIGH_INFERENCE_COST)
        assert len(candidates) >= 1
        for c in candidates:
            assert isinstance(c, NvidiaTechnologyCandidate)
            assert c.technology_name
            assert c.justification
            assert c.addresses_gap == TechnicalGap.HIGH_INFERENCE_COST

    def test_unknown_gap_returns_empty(self) -> None:
        candidates = map_gap_to_technologies("unknown_gap")  # type: ignore
        assert candidates == []

    def test_deterministic_output(self) -> None:
        first = map_gap_to_technologies(TechnicalGap.VOICE_NEED)
        second = map_gap_to_technologies(TechnicalGap.VOICE_NEED)
        assert len(first) == len(second)
        for a, b in zip(first, second, strict=True):
            assert a.technology_name == b.technology_name
            assert a.justification == b.justification


class TestBuildTechnologyCandidates:
    def test_only_detected_gaps_produce_candidates(self) -> None:
        gaps = [
            GapWithEvidence(
                gap=TechnicalGap.HIGH_INFERENCE_COST,
                detected=True,
                confidence=ConfidenceLevel.HIGH,
                evidence_tag=EvidenceTag.FACT,
                reasoning="detected",
                evidence_used=[],
            ),
            GapWithEvidence(
                gap=TechnicalGap.VOICE_NEED,
                detected=False,
                confidence=ConfidenceLevel.LOW,
                evidence_tag=EvidenceTag.HYPOTHESIS,
                reasoning="not detected",
                evidence_used=[],
            ),
        ]
        candidates = build_technology_candidates(gaps)
        techs = {c.technology_name for c in candidates}
        assert all("TensorRT" in t or "Triton" in t or "NIM" in t for t in techs)

    def test_no_detected_gaps_returns_empty(self) -> None:
        gaps = [
            GapWithEvidence(
                gap=TechnicalGap.VOICE_NEED,
                detected=False,
                confidence=ConfidenceLevel.LOW,
                evidence_tag=EvidenceTag.HYPOTHESIS,
                reasoning="not detected",
                evidence_used=[],
            ),
        ]
        candidates = build_technology_candidates(gaps)
        assert candidates == []


class TestMappingCoverage:
    def test_all_gaps_have_at_least_one_technology(self) -> None:
        for gap in TechnicalGap:
            candidates = map_gap_to_technologies(gap)
            assert len(candidates) >= 1, f"Gap {gap.value} has no technology mapping"

    def test_each_candidate_has_name_and_justification(self) -> None:
        for gap, mappings in _TECH_MATRIX.items():
            for tech_name, justification in mappings:
                assert tech_name, f"Empty tech name for gap {gap.value}"
                assert justification, f"Empty justification for tech {tech_name}"
