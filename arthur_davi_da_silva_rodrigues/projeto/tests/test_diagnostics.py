from app.classification.maturity import classify_ai_maturity
from app.diagnostics.gaps import diagnose_ai_stack_gaps
from app.extraction.startup import extract_startup_profile_from_source


def test_diagnose_ai_stack_gaps_detects_external_api_and_governance() -> None:
    text = (
        "MedAI automates healthcare workflows with AI agents and LLM copilots. "
        "The platform uses OpenAI APIs and has latency pressure."
    )
    profile = extract_startup_profile_from_source("https://medai.example", "MedAI", text)
    assessment = classify_ai_maturity(profile, text)

    report = diagnose_ai_stack_gaps(profile, assessment, text)
    gap_types = {gap.gap_type for gap in report.gaps}

    assert "external_api_dependency" in gap_types
    assert "agent_governance" in gap_types
    assert "healthcare_production_readiness" in gap_types
    assert report.summary.startswith("Foram detectados")


def test_diagnose_ai_stack_gaps_can_return_empty_report() -> None:
    text = "A simple marketplace for local services."
    profile = extract_startup_profile_from_source("https://local.example", "Local", text)
    assessment = classify_ai_maturity(profile, text)

    report = diagnose_ai_stack_gaps(profile, assessment, text)

    assert report.gaps == ()
    assert "Nenhum gap material" in report.summary


def test_diagnose_ai_stack_gaps_can_use_llm_response(monkeypatch) -> None:
    text = "MedAI usa agentes de IA para triagem e sofre com latência em produção."
    profile = extract_startup_profile_from_source("https://medai.example", "MedAI", text)
    assessment = classify_ai_maturity(profile, text)

    monkeypatch.setattr("app.diagnostics.gaps.is_llm_enabled", lambda settings: True)
    monkeypatch.setattr(
        "app.diagnostics.gaps.generate_openai_json",
        lambda **kwargs: {
            "summary": "Gap priorizado por LLM.",
            "gaps": [
                {
                    "gap_type": "inference_latency_or_cost",
                    "priority": "high",
                    "confidence": 0.92,
                    "evidence_basis": "evidence_backed",
                    "rationale": "A fonte cita latência em produção.",
                    "suggested_action": "Validar TensorRT-LLM e Triton.",
                }
            ],
        },
    )

    report = diagnose_ai_stack_gaps(profile, assessment, text)

    assert report.summary == "Gap priorizado por LLM."
    assert report.gaps[0].gap_type == "inference_latency_or_cost"
    assert report.gaps[0].priority == "high"
    assert report.gaps[0].confidence == 0.92
