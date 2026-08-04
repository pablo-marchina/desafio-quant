from radar.graph.edges import route_after_validation
from radar.graph.retry_policy import MAX_COLLECTION_ATTEMPTS, has_collection_retry_limit_reached
from radar.schemas import EvidenceValidationReport


def test_route_retries_collection_before_attempt_limit() -> None:
    state = {
        "collection_attempts": MAX_COLLECTION_ATTEMPTS - 1,
        "validation": _weak_validation(),
    }

    assert route_after_validation(state) == "scraper"


def test_route_stops_retrying_after_attempt_limit() -> None:
    state = {
        "collection_attempts": MAX_COLLECTION_ATTEMPTS,
        "validation": _weak_validation(),
    }

    assert has_collection_retry_limit_reached(state) is True
    assert route_after_validation(state) == "briefing"


def test_route_skips_retry_when_evidence_is_validated() -> None:
    state = {
        "collection_attempts": MAX_COLLECTION_ATTEMPTS,
        "validation": EvidenceValidationReport(
            has_minimum_evidence=True,
            source_quality="strong",
            supporting_evidence_ids=["claim_1", "claim_2"],
            conflicts=[],
            caveats=[],
            requires_human_review=False,
        ),
    }

    assert has_collection_retry_limit_reached(state) is False
    assert route_after_validation(state) == "classifier"


def _weak_validation() -> EvidenceValidationReport:
    return EvidenceValidationReport(
        has_minimum_evidence=False,
        source_quality="weak",
        supporting_evidence_ids=[],
        conflicts=[],
        caveats=["Need more evidence."],
        requires_human_review=True,
    )
