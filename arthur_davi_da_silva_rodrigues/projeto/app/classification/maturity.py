from __future__ import annotations

from app.classification.schemas import AiMaturityAssessmentDraft
from app.extraction.schemas import StartupProfileDraft
from app.llm.client import LlmUnavailableError, generate_openai_json, is_llm_enabled
from app.models.enums import AiMaturityLabel
from app.settings import get_settings

PROPRIETARY_DATA_TERMS = ("proprietary data", "dados proprietarios", "dados proprietários")
MODEL_CUSTOMIZATION_TERMS = ("fine-tuning", "finetuning", "custom model", "modelo proprio")
EVALUATION_TERMS = ("evaluation", "eval", "benchmark", "quality monitoring")
PRODUCTION_TERMS = ("production", "scale", "enterprise", "sla", "latency", "throughput")
GOVERNANCE_TERMS = ("guardrail", "governance", "compliance", "privacy", "security")
COST_LATENCY_TERMS = ("latency", "cost", "custo", "performance", "optimization")


def classify_ai_maturity(
    startup_profile: StartupProfileDraft,
    source_text: str | None = None,
) -> AiMaturityAssessmentDraft:
    settings = get_settings()
    if is_llm_enabled(settings):
        try:
            return _classify_with_llm(startup_profile, source_text or "")
        except (LlmUnavailableError, KeyError, TypeError, ValueError):
            pass

    return _classify_with_heuristics(startup_profile, source_text)


def _classify_with_heuristics(
    startup_profile: StartupProfileDraft,
    source_text: str | None = None,
) -> AiMaturityAssessmentDraft:
    normalized_text = " ".join(
        [
            startup_profile.description or "",
            startup_profile.ai_usage_summary or "",
            source_text or "",
        ]
    ).lower()
    scores = {
        "ai_workflow_depth": _score_ai_workflow_depth(startup_profile),
        "proprietary_data_advantage": _score_terms(normalized_text, PROPRIETARY_DATA_TERMS),
        "model_customization_or_evaluation": max(
            _score_terms(normalized_text, MODEL_CUSTOMIZATION_TERMS),
            _score_terms(normalized_text, EVALUATION_TERMS),
        ),
        "production_deployment_maturity": _score_terms(normalized_text, PRODUCTION_TERMS),
        "automation_depth": _score_automation_depth(startup_profile, normalized_text),
        "vendor_dependency_risk": _score_vendor_dependency(startup_profile),
        "governance_readiness": _score_terms(normalized_text, GOVERNANCE_TERMS),
        "cost_latency_sensitivity": _score_terms(normalized_text, COST_LATENCY_TERMS),
    }
    weighted_score = _weighted_score(scores)
    label = _label_for_score(weighted_score, startup_profile)
    confidence = _confidence_for_score(weighted_score, startup_profile)

    return AiMaturityAssessmentDraft(
        label=label,
        confidence=confidence,
        explanation=_build_explanation(label, scores, startup_profile),
        scores=scores,
    )


def _classify_with_llm(
    startup_profile: StartupProfileDraft,
    source_text: str,
) -> AiMaturityAssessmentDraft:
    settings = get_settings()
    response = generate_openai_json(
        settings=settings,
        system_prompt=(
            "Você é um avaliador de maturidade IA-native para NVIDIA. "
            "Use apenas evidências do perfil e texto fornecidos. "
            "Responda em JSON válido, sem markdown."
        ),
        user_prompt=(
            "Classifique a startup como ai_native, ai_enabled ou non_ai. "
            "Retorne JSON neste formato: "
            "{"
            '"label": string, "confidence": number, "explanation": string, '
            '"scores": {'
            '"ai_workflow_depth": number, '
            '"proprietary_data_advantage": number, '
            '"model_customization_or_evaluation": number, '
            '"production_deployment_maturity": number, '
            '"automation_depth": number, '
            '"vendor_dependency_risk": number, '
            '"governance_readiness": number, '
            '"cost_latency_sensitivity": number'
            "}"
            "}. Todos os scores devem estar entre 0 e 1. "
            f"Nome: {startup_profile.name}\n"
            f"Descrição: {startup_profile.description}\n"
            f"Resumo IA: {startup_profile.ai_usage_summary}\n"
            f"Setores: {', '.join(startup_profile.sectors)}\n"
            f"Sinais: {', '.join(startup_profile.technology_signals)}\n"
            f"Texto fonte:\n{source_text[:6000]}"
        ),
    )
    scores = _llm_scores(response.get("scores"))
    return AiMaturityAssessmentDraft(
        label=_label_from_llm(response.get("label")),
        confidence=_float_between_zero_and_one(response.get("confidence")),
        explanation=_string_value(response.get("explanation")) or "Classificação gerada por LLM.",
        scores=scores,
    )


def _llm_scores(value: object) -> dict[str, float]:
    expected_keys = (
        "ai_workflow_depth",
        "proprietary_data_advantage",
        "model_customization_or_evaluation",
        "production_deployment_maturity",
        "automation_depth",
        "vendor_dependency_risk",
        "governance_readiness",
        "cost_latency_sensitivity",
    )
    raw_scores = value if isinstance(value, dict) else {}
    return {
        key: _float_between_zero_and_one(raw_scores.get(key))
        for key in expected_keys
    }


def _label_from_llm(value: object) -> str:
    label = _string_value(value)
    if label in {
        AiMaturityLabel.AI_NATIVE,
        AiMaturityLabel.AI_ENABLED,
        AiMaturityLabel.NON_AI,
    }:
        return label
    return AiMaturityLabel.NON_AI


def _string_value(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _float_between_zero_and_one(value: object) -> float:
    if not isinstance(value, (int, float)):
        return 0.5
    return max(0.0, min(float(value), 1.0))


def _score_ai_workflow_depth(startup_profile: StartupProfileDraft) -> float:
    if not startup_profile.ai_usage_summary:
        return 0.0

    technology_score = min(len(startup_profile.technology_signals) / 3, 1.0)
    accepted_claim_bonus = 0.2 if startup_profile.accepted_claims else 0.0
    return min(0.45 + technology_score * 0.35 + accepted_claim_bonus, 1.0)


def _score_automation_depth(startup_profile: StartupProfileDraft, normalized_text: str) -> float:
    automation_terms = ("automate", "automation", "automação", "workflow", "agent", "agents")
    term_score = _score_terms(normalized_text, automation_terms)
    agent_bonus = 0.25 if "AI agents" in startup_profile.technology_signals else 0.0
    return min(term_score + agent_bonus, 1.0)


def _score_vendor_dependency(startup_profile: StartupProfileDraft) -> float:
    return 1.0 if "External AI API" in startup_profile.technology_signals else 0.0


def _score_terms(normalized_text: str, terms: tuple[str, ...]) -> float:
    matches = sum(1 for term in terms if term in normalized_text)
    if matches == 0:
        return 0.0
    return min(0.35 + matches * 0.2, 1.0)


def _weighted_score(scores: dict[str, float]) -> float:
    weights = {
        "ai_workflow_depth": 0.28,
        "automation_depth": 0.18,
        "model_customization_or_evaluation": 0.14,
        "production_deployment_maturity": 0.12,
        "proprietary_data_advantage": 0.10,
        "governance_readiness": 0.08,
        "cost_latency_sensitivity": 0.06,
        "vendor_dependency_risk": 0.04,
    }
    return sum(scores[key] * weight for key, weight in weights.items())


def _label_for_score(weighted_score: float, startup_profile: StartupProfileDraft) -> str:
    if weighted_score >= 0.56 and startup_profile.ai_usage_summary:
        return AiMaturityLabel.AI_NATIVE
    if weighted_score >= 0.25 or startup_profile.ai_usage_summary:
        return AiMaturityLabel.AI_ENABLED
    return AiMaturityLabel.NON_AI


def _confidence_for_score(
    weighted_score: float,
    startup_profile: StartupProfileDraft,
) -> float:
    evidence_factor = min(len(startup_profile.evidence_claims) / 5, 1.0)
    return min(0.45 + weighted_score * 0.35 + evidence_factor * 0.2, 0.95)


def _build_explanation(
    label: str,
    scores: dict[str, float],
    startup_profile: StartupProfileDraft,
) -> str:
    strongest_dimensions = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:3]
    dimensions = ", ".join(
        _score_label(name) for name, score in strongest_dimensions if score > 0
    )
    technology_signals = (
        ", ".join(_signal_label(signal) for signal in startup_profile.technology_signals)
        or "sem sinais de IA"
    )
    return (
        f"Classificada como {_label_text(label)} com base em {technology_signals}. "
        f"Dimensões mais fortes: {dimensions or 'nenhuma'}."
    )


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


def _label_text(label: str) -> str:
    return {
        "ai_native": "IA-native",
        "ai_enabled": "IA aplicada",
        "non_ai": "sem sinais fortes de IA",
    }.get(label, label)


def _signal_label(signal: str) -> str:
    return {
        "AI agents": "agentes de IA",
        "Computer vision": "visão computacional",
        "Speech AI": "IA de voz",
        "Data pipeline": "pipeline de dados",
        "External AI API": "API externa de IA",
    }.get(signal, signal)
