from app.classification.maturity import classify_ai_maturity
from app.extraction.startup import extract_startup_profile_from_source
from app.models.enums import AiMaturityLabel


def test_classify_ai_native_when_ai_is_core_to_workflow() -> None:
    text = (
        "MedAI automates healthcare workflows with AI agents and LLM copilots. "
        "The platform uses proprietary data, evaluation benchmarks, latency monitoring, "
        "and production guardrails."
    )
    profile = extract_startup_profile_from_source("https://medai.example", "MedAI", text)

    assessment = classify_ai_maturity(profile, text)

    assert assessment.label == AiMaturityLabel.AI_NATIVE
    assert assessment.confidence > 0.6
    assert assessment.scores["ai_workflow_depth"] > 0
    assert assessment.scores["automation_depth"] > 0


def test_classify_non_ai_when_no_ai_evidence_exists() -> None:
    text = "A marketplace for local services and scheduling."
    profile = extract_startup_profile_from_source("https://local.example", "Local", text)

    assessment = classify_ai_maturity(profile, text)

    assert assessment.label == AiMaturityLabel.NON_AI
    assert assessment.scores["ai_workflow_depth"] == 0


def test_classify_ai_maturity_can_use_llm_response(monkeypatch) -> None:
    text = "Clara AI usa agentes de IA em workflow clínico."
    profile = extract_startup_profile_from_source("https://clara.example", "Clara AI", text)
    monkeypatch.setattr("app.classification.maturity.is_llm_enabled", lambda settings: True)
    monkeypatch.setattr(
        "app.classification.maturity.generate_openai_json",
        lambda **kwargs: {
            "label": AiMaturityLabel.AI_NATIVE,
            "confidence": 0.88,
            "explanation": "IA é central ao workflow clínico.",
            "scores": {
                "ai_workflow_depth": 0.9,
                "proprietary_data_advantage": 0.5,
                "model_customization_or_evaluation": 0.4,
                "production_deployment_maturity": 0.6,
                "automation_depth": 0.85,
                "vendor_dependency_risk": 0.3,
                "governance_readiness": 0.5,
                "cost_latency_sensitivity": 0.7,
            },
        },
    )

    assessment = classify_ai_maturity(profile, text)

    assert assessment.label == AiMaturityLabel.AI_NATIVE
    assert assessment.confidence == 0.88
    assert assessment.scores["ai_workflow_depth"] == 0.9
