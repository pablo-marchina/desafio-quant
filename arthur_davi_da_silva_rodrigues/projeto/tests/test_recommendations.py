from app.classification.maturity import classify_ai_maturity
from app.diagnostics.gaps import diagnose_ai_stack_gaps
from app.diagnostics.schemas import GapDiagnosis
from app.extraction.startup import extract_startup_profile_from_source
from app.recommendations.engine import generate_recommendations


def test_generate_recommendations_maps_gaps_to_nvidia_technologies() -> None:
    text = (
        "MedAI automates healthcare workflows with AI agents and LLM copilots. "
        "The platform uses OpenAI APIs and has latency pressure."
    )
    profile = extract_startup_profile_from_source("https://medai.example", "MedAI", text)
    assessment = classify_ai_maturity(profile, text)
    gap_report = diagnose_ai_stack_gaps(profile, assessment, text)

    recommendation_report = generate_recommendations(gap_report.gaps)
    technology_names = {
        recommendation.technology_name
        for recommendation in recommendation_report.recommendations
    }

    assert "NVIDIA NIM" in technology_names
    assert "TensorRT-LLM" in technology_names
    assert "NeMo Guardrails" in technology_names
    assert "NVIDIA Clara" in technology_names
    assert recommendation_report.summary.startswith("Foram geradas")


def test_generate_recommendations_returns_empty_report_without_gaps() -> None:
    recommendation_report = generate_recommendations(())

    assert recommendation_report.recommendations == ()
    assert "Nenhuma recomendação" in recommendation_report.summary


def test_generate_recommendations_can_use_llm_response(monkeypatch) -> None:
    monkeypatch.setattr("app.recommendations.engine.is_llm_enabled", lambda settings: True)
    monkeypatch.setattr(
        "app.recommendations.engine.generate_openai_json",
        lambda **kwargs: {
            "summary": "Recomendações priorizadas por LLM.",
            "recommendations": [
                {
                    "gap_type": "inference_latency_or_cost",
                    "technology_name": "TensorRT-LLM",
                    "priority": "high",
                    "complexity": "high",
                    "technical_rationale": "Otimiza inferência de LLM em produção.",
                    "business_rationale": "Reduz custo e latência para escalar o produto.",
                    "next_action": "Rodar benchmark com modelo e tráfego reais.",
                }
            ],
        },
    )
    gaps = (
        GapDiagnosis(
            gap_type="inference_latency_or_cost",
            priority="high",
            confidence=0.9,
            evidence_basis="evidence_backed",
            rationale="Latência citada na fonte.",
            suggested_action="Validar otimização de inferência.",
        ),
    )

    recommendation_report = generate_recommendations(gaps)

    assert recommendation_report.summary == "Recomendações priorizadas por LLM."
    assert recommendation_report.recommendations[0].technology_name == "TensorRT-LLM"
    assert recommendation_report.recommendations[0].priority == "high"
