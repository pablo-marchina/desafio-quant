from app.extraction.startup import extract_startup_profile_from_source
from app.models.enums import ClaimValidationStatus


def test_extract_startup_profile_from_source_detects_ai_sector_and_technology() -> None:
    text = (
        "MedAI automates healthcare workflows with AI agents and LLM copilots. "
        "The platform helps hospitals reduce manual triage work using OpenAI APIs."
    )

    profile = extract_startup_profile_from_source(
        url="https://medai.example",
        title="MedAI - AI for hospitals",
        extracted_text=text,
    )

    assert profile.name == "MedAI"
    assert profile.description.startswith("MedAI automates healthcare")
    assert profile.ai_usage_summary is not None
    assert "healthcare" in profile.sectors
    assert "LLM" in profile.technology_signals
    assert "AI agents" in profile.technology_signals
    assert "External AI API" in profile.technology_signals
    assert any(claim.claim_type == "ai_usage" for claim in profile.evidence_claims)
    assert any(
        claim.validation_status == ClaimValidationStatus.ACCEPTED
        for claim in profile.evidence_claims
    )
    assert profile.accepted_claims
    assert profile.review_claims


def test_extract_startup_profile_falls_back_to_domain_name() -> None:
    profile = extract_startup_profile_from_source(
        url="https://example-startup.com",
        title=None,
        extracted_text="No AI terms here.",
    )

    assert profile.name == "Example Startup"


def test_extract_startup_profile_deduplicates_claims() -> None:
    text = (
        "AI agents automate healthcare workflows. "
        "AI agents automate healthcare workflows with LLM copilots."
    )

    profile = extract_startup_profile_from_source(
        url="https://medai.example",
        title="MedAI",
        extracted_text=text,
    )

    claim_keys = {(claim.claim_type, claim.claim) for claim in profile.evidence_claims}
    assert len(claim_keys) == len(profile.evidence_claims)


def test_extract_startup_profile_can_use_llm_response(monkeypatch) -> None:
    monkeypatch.setattr("app.extraction.startup.is_llm_enabled", lambda settings: True)
    monkeypatch.setattr(
        "app.extraction.startup.generate_openai_json",
        lambda **kwargs: {
            "name": "Clara AI",
            "description": "Plataforma de agentes para documentação clínica.",
            "ai_usage_summary": "Usa agentes de IA e LLMs em workflows clínicos.",
            "sectors": ["healthcare"],
            "technology_signals": ["LLM", "AI agents"],
            "evidence_claims": [
                {
                    "claim": "A startup usa agentes de IA.",
                    "claim_type": "ai_usage",
                    "supporting_text": "agentes de IA e LLMs",
                    "confidence": 0.91,
                }
            ],
        },
    )

    profile = extract_startup_profile_from_source(
        url="https://clara.example",
        title="Clara",
        extracted_text="Texto público.",
    )

    assert profile.name == "Clara AI"
    assert profile.sectors == ("healthcare",)
    assert profile.technology_signals == ("LLM", "AI agents")
    assert profile.accepted_claims
