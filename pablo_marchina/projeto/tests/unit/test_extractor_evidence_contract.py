from __future__ import annotations

from src.agents.extractor_agent import _build_evidence_item
from src.extraction.schemas import Evidence, SourceType, StartupProfile


def test_extracted_evidence_satisfies_validator_contract() -> None:
    profile = StartupProfile(
        startup_name="Example AI",
        website="https://example.ai/",
        country="Brazil",
        sector="Generative AI",
        description="Example AI builds production AI systems.",
        product_summary="AI agents for enterprise workflows.",
        ai_signals=["artificial intelligence", "agents"],
        tech_stack_signals=["LLM"],
        confidence_score=0.9,
    )
    item = _build_evidence_item(
        {
            "source_id": "official",
            "source_url": "https://example.ai/",
            "text": "Example AI provides artificial intelligence agents for enterprise workflows.",
            "fetched_at": "2026-08-03T00:00:00+00:00",
        },
        profile,
        SourceType.OFFICIAL_SITE,
    )

    evidence = Evidence.model_validate(item)
    assert evidence.claim.startswith("Example AI:")
    assert "artificial intelligence" in evidence.quote_or_evidence
    assert evidence.confidence.value == "high"
    assert evidence.collected_at.isoformat() == "2026-08-03T00:00:00+00:00"
