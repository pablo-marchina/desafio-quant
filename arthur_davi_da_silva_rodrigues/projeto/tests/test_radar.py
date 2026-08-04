from app.classification.maturity import classify_ai_maturity
from app.diagnostics.gaps import diagnose_ai_stack_gaps
from app.extraction.startup import extract_startup_profile_from_source
from app.radar.scoring import score_threat_opportunity_radar
from app.recommendations.engine import generate_recommendations


def test_score_threat_opportunity_radar_flags_wrapper_risk_and_fit() -> None:
    text = (
        "MedAI automates healthcare workflows with AI agents and LLM copilots. "
        "The platform uses OpenAI APIs and has latency pressure."
    )
    profile = extract_startup_profile_from_source("https://medai.example", "MedAI", text)
    assessment = classify_ai_maturity(profile, text)
    gap_report = diagnose_ai_stack_gaps(profile, assessment, text)
    recommendation_report = generate_recommendations(gap_report.gaps)

    radar = score_threat_opportunity_radar(
        startup_profile=profile,
        assessment=assessment,
        gap_report=gap_report,
        recommendation_report=recommendation_report,
    )

    assert radar.wrapper_risk >= 0.7
    assert radar.nvidia_fit >= 0.7
    assert radar.outreach_urgency >= 0.7
    assert "Redução de risco de wrapper" in radar.recommended_focus


def test_score_threat_opportunity_radar_handles_low_signal_startup() -> None:
    text = "A marketplace for local services."
    profile = extract_startup_profile_from_source("https://local.example", "Local", text)
    assessment = classify_ai_maturity(profile, text)
    gap_report = diagnose_ai_stack_gaps(profile, assessment, text)
    recommendation_report = generate_recommendations(gap_report.gaps)

    radar = score_threat_opportunity_radar(
        startup_profile=profile,
        assessment=assessment,
        gap_report=gap_report,
        recommendation_report=recommendation_report,
    )

    assert radar.nvidia_fit == 0
    assert radar.outreach_urgency == 0


def test_score_threat_opportunity_radar_can_use_llm_response(monkeypatch) -> None:
    text = (
        "MedAI automates healthcare workflows with AI agents and LLM copilots. "
        "The platform uses OpenAI APIs and has latency pressure."
    )
    profile = extract_startup_profile_from_source("https://medai.example", "MedAI", text)
    assessment = classify_ai_maturity(profile, text)
    gap_report = diagnose_ai_stack_gaps(profile, assessment, text)
    recommendation_report = generate_recommendations(gap_report.gaps)

    monkeypatch.setattr("app.radar.scoring.is_llm_enabled", lambda settings: True)
    monkeypatch.setattr(
        "app.radar.scoring.generate_openai_json",
        lambda **kwargs: {
            "wrapper_risk": 0.81,
            "defensibility": 0.47,
            "nvidia_fit": 0.88,
            "outreach_urgency": 0.9,
            "summary": "Radar estratégico gerado por LLM.",
            "recommended_focus": ["TensorRT-LLM", "NVIDIA NIM"],
        },
    )

    radar = score_threat_opportunity_radar(
        startup_profile=profile,
        assessment=assessment,
        gap_report=gap_report,
        recommendation_report=recommendation_report,
    )

    assert radar.summary == "Radar estratégico gerado por LLM."
    assert radar.wrapper_risk == 0.81
    assert radar.nvidia_fit == 0.88
    assert radar.recommended_focus == ("TensorRT-LLM", "NVIDIA NIM")
