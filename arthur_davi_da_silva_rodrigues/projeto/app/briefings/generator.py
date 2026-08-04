from app.classification.schemas import AiMaturityAssessmentDraft
from app.diagnostics.schemas import GapDiagnosisReport
from app.extraction.schemas import StartupProfileDraft
from app.radar.schemas import ThreatOpportunityRadar
from app.recommendations.schemas import RecommendationReport


def generate_executive_briefing(
    startup_profile: StartupProfileDraft,
    assessment: AiMaturityAssessmentDraft,
    gap_report: GapDiagnosisReport,
    recommendation_report: RecommendationReport,
    radar: ThreatOpportunityRadar | None = None,
) -> str:
    startup_name = startup_profile.name or "Startup desconhecida"
    sections = [
        f"# {startup_name} - Relatório NVIDIA Startup AI Radar",
        _startup_overview(startup_profile),
        _maturity_section(assessment),
        _evidence_section(startup_profile),
        _radar_section(radar),
        _gap_section(gap_report),
        _recommendation_section(recommendation_report),
        _next_action_section(recommendation_report),
        _sources_section(startup_profile),
    ]
    return "\n\n".join(section for section in sections if section)


def _startup_overview(startup_profile: StartupProfileDraft) -> str:
    sectors = (
        ", ".join(_sector_label(sector) for sector in startup_profile.sectors)
        or "não detectado"
    )
    technology_signals = (
        ", ".join(_signal_label(signal) for signal in startup_profile.technology_signals)
        or "não detectado"
    )
    description = startup_profile.description or "Nenhuma descrição extraída."

    return "\n".join(
        [
            "## Visão geral da startup",
            f"- Website: {startup_profile.website}",
            f"- Setores: {sectors}",
            f"- Sinais tecnológicos: {technology_signals}",
            f"- Descrição: {description}",
        ]
    )


def _maturity_section(assessment: AiMaturityAssessmentDraft) -> str:
    score_lines = [
        f"- {_score_label(score_name)}: {score_value:.2f}"
        for score_name, score_value in assessment.scores.items()
    ]
    return "\n".join(
        [
            "## Maturidade IA-native",
            f"- Classificação: {_maturity_label(assessment.label)}",
            f"- Confiança: {assessment.confidence:.2f}",
            f"- Explicação: {assessment.explanation}",
            "",
            "### Detalhamento dos scores",
            *score_lines,
        ]
    )


def _evidence_section(startup_profile: StartupProfileDraft) -> str:
    if not startup_profile.evidence_claims:
        return "## Evidências\nNenhuma evidência foi extraída."

    claim_lines = [
        (
            f"- [{_validation_label(claim.validation_status)}] {claim.claim} "
            f"(confiança {claim.confidence:.2f}) - {claim.supporting_text}"
        )
        for claim in startup_profile.evidence_claims
    ]
    return "\n".join(["## Evidências", *claim_lines])


def _radar_section(radar: ThreatOpportunityRadar | None) -> str:
    if radar is None:
        return ""

    focus = ", ".join(radar.recommended_focus) or "nenhum foco recomendado"
    return "\n".join(
        [
            "## Radar estratégico",
            f"- Risco de wrapper: {radar.wrapper_risk:.2f}",
            f"- Defensibilidade: {radar.defensibility:.2f}",
            f"- Fit NVIDIA: {radar.nvidia_fit:.2f}",
            f"- Urgência de outreach: {radar.outreach_urgency:.2f}",
            f"- Síntese: {radar.summary}",
            f"- Foco recomendado: {focus}",
        ]
    )


def _gap_section(gap_report: GapDiagnosisReport) -> str:
    if not gap_report.gaps:
        return f"## Gaps de stack de IA\n{gap_report.summary}"

    gap_lines = [
        (
            f"- [{_priority_label(gap.priority)}] {_gap_label(gap.gap_type)} "
            f"({_basis_label(gap.evidence_basis)}, confiança {gap.confidence:.2f}): "
            f"{gap.rationale}"
        )
        for gap in gap_report.gaps
    ]
    return "\n".join(["## Gaps de stack de IA", gap_report.summary, *gap_lines])


def _recommendation_section(recommendation_report: RecommendationReport) -> str:
    if not recommendation_report.recommendations:
        return f"## Fit NVIDIA\n{recommendation_report.summary}"

    recommendation_lines = [
        (
            f"- [{_priority_label(recommendation.priority)}] {recommendation.technology_name} "
            f"para {_gap_label(recommendation.gap_type)} "
            f"(complexidade {_complexity_label(recommendation.complexity)}): "
            f"{recommendation.technical_rationale}"
        )
        for recommendation in recommendation_report.recommendations
    ]
    return "\n".join(["## Fit NVIDIA", recommendation_report.summary, *recommendation_lines])


def _next_action_section(recommendation_report: RecommendationReport) -> str:
    if not recommendation_report.recommendations:
        return "## Próxima ação recomendada\nNenhuma próxima ação gerada."

    top_recommendation = recommendation_report.recommendations[0]
    return "\n".join(
        [
            "## Próxima ação recomendada",
            top_recommendation.next_action,
        ]
    )


def _sources_section(startup_profile: StartupProfileDraft) -> str:
    return "\n".join(["## Fontes", f"- {startup_profile.website}"])


def _maturity_label(label: str) -> str:
    return {
        "ai_native": "IA-native",
        "ai_enabled": "IA aplicada",
        "non_ai": "Sem sinais fortes de IA",
    }.get(label, label)


def _priority_label(priority: str) -> str:
    return {
        "high": "alta",
        "medium": "média",
        "low": "baixa",
    }.get(priority, priority)


def _complexity_label(complexity: str) -> str:
    return {
        "high": "alta",
        "medium": "média",
        "low": "baixa",
    }.get(complexity, complexity)


def _basis_label(evidence_basis: str) -> str:
    return {
        "evidence_backed": "com evidência",
        "inferred": "inferido",
    }.get(evidence_basis, evidence_basis)


def _validation_label(validation_status: str) -> str:
    return {
        "accepted": "aceita",
        "needs_review": "revisar",
        "pending": "pendente",
        "rejected": "rejeitada",
    }.get(validation_status, validation_status)


def _gap_label(gap_type: str) -> str:
    return {
        "external_api_dependency": "dependência de API externa",
        "inference_latency_or_cost": "custo ou latência de inferência",
        "model_serving_maturity": "maturidade de serving",
        "agent_governance": "governança de agentes",
        "data_pipeline_scale": "escala de dados",
        "voice_ai_maturity": "maturidade em voz",
        "healthcare_production_readiness": "prontidão de saúde em produção",
        "robotics_or_simulation": "robótica ou simulação",
        "cybersecurity_ai": "IA para cibersegurança",
    }.get(gap_type, gap_type)


def _sector_label(sector: str) -> str:
    return {
        "healthcare": "saúde",
        "finance": "finanças",
        "cybersecurity": "cibersegurança",
        "retail": "varejo",
        "education": "educação",
        "legal": "jurídico",
        "robotics": "robótica",
    }.get(sector, sector)


def _signal_label(signal: str) -> str:
    return {
        "AI agents": "agentes de IA",
        "Computer vision": "visão computacional",
        "Speech AI": "IA de voz",
        "Data pipeline": "pipeline de dados",
        "External AI API": "API externa de IA",
    }.get(signal, signal)


def _score_label(score_name: str) -> str:
    return {
        "ai_workflow_depth": "profundidade do uso de IA",
        "proprietary_data_advantage": "vantagem de dados próprios",
        "model_customization_or_evaluation": "customização ou avaliação",
        "production_deployment_maturity": "maturidade em produção",
        "automation_depth": "profundidade da automação",
        "vendor_dependency_risk": "dependência de fornecedor",
        "governance_readiness": "governança",
        "cost_latency_sensitivity": "sensibilidade a custo/latência",
    }.get(score_name, score_name)
