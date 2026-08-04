from radar.agents.extractor import extract_startups_and_claims
from radar.agents.validator import validate_evidence
from radar.schemas import SearchPlan
from radar.scraping.collectors import StaticSeedCollector


def test_extractor_marks_ai_usage_claims_from_public_sources() -> None:
    collector = StaticSeedCollector()
    sources = collector.collect(
        SearchPlan(
            query="startup validada com duas fontes de IA",
            keywords=["startup", "IA"],
            source_types=["official_site", "news"],
            collection_plan=["collect deterministic sources"],
        )
    )

    startups, claims = extract_startups_and_claims({"query": "startup validada", "sources": sources})

    assert startups[0].ai_usage_summary is not None
    assert [claim.claim_type for claim in claims].count("ai_usage") >= 2


def test_validator_requires_independent_ai_evidence_before_recommendations() -> None:
    collector = StaticSeedCollector()
    sources = collector.collect(
        SearchPlan(
            query="startup brasileira de IA",
            keywords=["startup", "IA"],
            source_types=["nvidia_documentation"],
            collection_plan=["collect deterministic sources"],
        )
    )
    _, claims = extract_startups_and_claims({"query": "startup brasileira de IA", "sources": sources})

    validation = validate_evidence({"sources": sources, "claims": claims})

    assert validation.has_minimum_evidence is False
    assert validation.source_quality == "weak"
    assert "Need at least two independent public evidence claims before recommendations." in validation.caveats
    assert "Need at least one validated AI usage claim before recommendations." in validation.caveats
