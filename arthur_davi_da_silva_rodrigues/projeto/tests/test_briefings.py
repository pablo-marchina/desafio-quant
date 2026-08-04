from app.briefings.generator import generate_executive_briefing
from app.classification.maturity import classify_ai_maturity
from app.diagnostics.gaps import diagnose_ai_stack_gaps
from app.extraction.startup import extract_startup_profile_from_source
from app.recommendations.engine import generate_recommendations


def test_generate_executive_briefing_contains_required_sections() -> None:
    text = (
        "MedAI automates healthcare workflows with AI agents and LLM copilots. "
        "The platform uses OpenAI APIs and has latency pressure."
    )
    profile = extract_startup_profile_from_source("https://medai.example", "MedAI", text)
    assessment = classify_ai_maturity(profile, text)
    gap_report = diagnose_ai_stack_gaps(profile, assessment, text)
    recommendation_report = generate_recommendations(gap_report.gaps)

    markdown = generate_executive_briefing(
        startup_profile=profile,
        assessment=assessment,
        gap_report=gap_report,
        recommendation_report=recommendation_report,
    )

    assert "# MedAI - Relatório NVIDIA Startup AI Radar" in markdown
    assert "## Visão geral da startup" in markdown
    assert "## Maturidade IA-native" in markdown
    assert "## Evidências" in markdown
    assert "## Gaps de stack de IA" in markdown
    assert "## Fit NVIDIA" in markdown
    assert "## Próxima ação recomendada" in markdown
    assert "## Fontes" in markdown
