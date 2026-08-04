from src.extraction.schemas import TechnicalGap

ALL_TECHNICAL_GAPS: tuple[TechnicalGap, ...] = tuple(TechnicalGap)


def test_gap_taxonomy_contains_expected_gaps() -> None:
    assert TechnicalGap.HIGH_LATENCY in ALL_TECHNICAL_GAPS
    assert TechnicalGap.AI_CYBERSECURITY_NEED in ALL_TECHNICAL_GAPS
    assert len(ALL_TECHNICAL_GAPS) == 15
