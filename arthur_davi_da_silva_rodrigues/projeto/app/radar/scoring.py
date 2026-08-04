from app.classification.schemas import AiMaturityAssessmentDraft
from app.diagnostics.schemas import GapDiagnosisReport
from app.extraction.schemas import StartupProfileDraft
from app.llm.client import LlmUnavailableError, generate_openai_json, is_llm_enabled
from app.models.enums import RecommendationPriority
from app.radar.schemas import ThreatOpportunityRadar
from app.recommendations.schemas import RecommendationReport
from app.settings import get_settings


def score_threat_opportunity_radar(
    startup_profile: StartupProfileDraft,
    assessment: AiMaturityAssessmentDraft,
    gap_report: GapDiagnosisReport,
    recommendation_report: RecommendationReport,
) -> ThreatOpportunityRadar:
    settings = get_settings()
    if is_llm_enabled(settings):
        try:
            return _score_with_llm(
                startup_profile,
                assessment,
                gap_report,
                recommendation_report,
            )
        except (LlmUnavailableError, KeyError, TypeError, ValueError):
            pass

    return _score_with_heuristics(
        startup_profile,
        assessment,
        gap_report,
        recommendation_report,
    )


def _score_with_heuristics(
    startup_profile: StartupProfileDraft,
    assessment: AiMaturityAssessmentDraft,
    gap_report: GapDiagnosisReport,
    recommendation_report: RecommendationReport,
) -> ThreatOpportunityRadar:
    wrapper_risk = _score_wrapper_risk(startup_profile, assessment, gap_report)
    defensibility = _score_defensibility(startup_profile, assessment)
    nvidia_fit = _score_nvidia_fit(recommendation_report)
    outreach_urgency = _score_outreach_urgency(gap_report, nvidia_fit)

    return ThreatOpportunityRadar(
        wrapper_risk=wrapper_risk,
        defensibility=defensibility,
        nvidia_fit=nvidia_fit,
        outreach_urgency=outreach_urgency,
        summary=_build_summary(wrapper_risk, defensibility, nvidia_fit, outreach_urgency),
        recommended_focus=_recommended_focus(gap_report, recommendation_report),
    )


def _score_with_llm(
    startup_profile: StartupProfileDraft,
    assessment: AiMaturityAssessmentDraft,
    gap_report: GapDiagnosisReport,
    recommendation_report: RecommendationReport,
) -> ThreatOpportunityRadar:
    settings = get_settings()
    recommendation_names = [
        recommendation.technology_name
        for recommendation in recommendation_report.recommendations
    ]
    response = generate_openai_json(
        settings=settings,
        system_prompt=(
            "Você é um analista estratégico da NVIDIA avaliando ameaça e oportunidade "
            "em startups IA-native. Responda apenas JSON válido."
        ),
        user_prompt=(
            "Retorne JSON no formato: "
            '{"wrapper_risk": number, "defensibility": number, "nvidia_fit": number, '
            '"outreach_urgency": number, "summary": string, '
            '"recommended_focus": string[]}. '
            "Todos os scores devem estar entre 0 e 1. "
            f"Startup: {startup_profile.name}\n"
            f"Descrição: {startup_profile.description}\n"
            f"Sinais: {', '.join(startup_profile.technology_signals)}\n"
            f"Maturidade: {assessment.label}, scores={assessment.scores}\n"
            f"Gaps: {[gap.gap_type for gap in gap_report.gaps]}\n"
            f"Recomendações: {recommendation_names}"
        ),
    )
    return ThreatOpportunityRadar(
        wrapper_risk=_float_between_zero_and_one(response.get("wrapper_risk")),
        defensibility=_float_between_zero_and_one(response.get("defensibility")),
        nvidia_fit=_float_between_zero_and_one(response.get("nvidia_fit")),
        outreach_urgency=_float_between_zero_and_one(response.get("outreach_urgency")),
        summary=_string_value(response.get("summary")) or "Radar gerado por LLM.",
        recommended_focus=tuple(_string_list(response.get("recommended_focus"))),
    )


def _string_value(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _float_between_zero_and_one(value: object) -> float:
    if not isinstance(value, int | float):
        return 0.5
    return max(0.0, min(float(value), 1.0))


def _score_wrapper_risk(
    startup_profile: StartupProfileDraft,
    assessment: AiMaturityAssessmentDraft,
    gap_report: GapDiagnosisReport,
) -> float:
    external_api_gap = any(gap.gap_type == "external_api_dependency" for gap in gap_report.gaps)
    api_signal = "External AI API" in startup_profile.technology_signals
    proprietary_data = assessment.scores.get("proprietary_data_advantage", 0)
    customization = assessment.scores.get("model_customization_or_evaluation", 0)

    risk = 0.2
    if external_api_gap or api_signal:
        risk += 0.45
    if proprietary_data < 0.25:
        risk += 0.2
    if customization < 0.25:
        risk += 0.15

    return min(risk, 1.0)


def _score_defensibility(
    startup_profile: StartupProfileDraft,
    assessment: AiMaturityAssessmentDraft,
) -> float:
    signal_depth = min(len(startup_profile.technology_signals) / 4, 1.0)
    data_score = assessment.scores.get("proprietary_data_advantage", 0)
    customization_score = assessment.scores.get("model_customization_or_evaluation", 0)
    governance_score = assessment.scores.get("governance_readiness", 0)
    workflow_score = assessment.scores.get("ai_workflow_depth", 0)

    return min(
        workflow_score * 0.35
        + signal_depth * 0.2
        + data_score * 0.2
        + customization_score * 0.15
        + governance_score * 0.1,
        1.0,
    )


def _score_nvidia_fit(recommendation_report: RecommendationReport) -> float:
    if not recommendation_report.recommendations:
        return 0.0

    high_priority_count = sum(
        1
        for recommendation in recommendation_report.recommendations
        if recommendation.priority == RecommendationPriority.HIGH
    )
    breadth_score = min(len(recommendation_report.recommendations) / 6, 1.0)
    priority_score = min(high_priority_count / 4, 1.0)
    return min(0.35 + breadth_score * 0.35 + priority_score * 0.3, 1.0)


def _score_outreach_urgency(
    gap_report: GapDiagnosisReport,
    nvidia_fit: float,
) -> float:
    high_priority_gap_count = sum(
        1 for gap in gap_report.gaps if gap.priority == RecommendationPriority.HIGH
    )
    urgency = min(high_priority_gap_count / 5, 1.0) * 0.65 + nvidia_fit * 0.35
    return min(urgency, 1.0)


def _build_summary(
    wrapper_risk: float,
    defensibility: float,
    nvidia_fit: float,
    outreach_urgency: float,
) -> str:
    if outreach_urgency >= 0.75 and nvidia_fit >= 0.75:
        return "Alvo de outreach NVIDIA de alta prioridade, com forte fit técnico."
    if wrapper_risk >= 0.7 and defensibility < 0.5:
        return "Alto risco de wrapper; NVIDIA pode ajudar a aumentar a defensibilidade."
    if defensibility >= 0.65:
        return "Perfil IA-native promissor, com sinais relevantes de defensibilidade."
    return "Oportunidade moderada; colete mais evidências antes de priorizar outreach."


def _recommended_focus(
    gap_report: GapDiagnosisReport,
    recommendation_report: RecommendationReport,
) -> tuple[str, ...]:
    focus_items = [
        recommendation.technology_name
        for recommendation in recommendation_report.recommendations[:4]
    ]
    if any(gap.gap_type == "external_api_dependency" for gap in gap_report.gaps):
        focus_items.append("Redução de risco de wrapper")

    return tuple(dict.fromkeys(focus_items))
