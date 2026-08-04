from app.classification.schemas import AiMaturityAssessmentDraft
from app.diagnostics.schemas import GapDiagnosis, GapDiagnosisReport
from app.extraction.schemas import StartupProfileDraft
from app.llm.client import LlmUnavailableError, generate_openai_json, is_llm_enabled
from app.models.enums import RecommendationPriority
from app.settings import get_settings


def diagnose_ai_stack_gaps(
    startup_profile: StartupProfileDraft,
    assessment: AiMaturityAssessmentDraft,
    source_text: str | None = None,
) -> GapDiagnosisReport:
    settings = get_settings()
    if is_llm_enabled(settings):
        try:
            return _diagnose_with_llm(startup_profile, assessment, source_text or "")
        except (LlmUnavailableError, KeyError, TypeError, ValueError):
            pass

    return _diagnose_with_heuristics(startup_profile, assessment, source_text)


def _diagnose_with_heuristics(
    startup_profile: StartupProfileDraft,
    assessment: AiMaturityAssessmentDraft,
    source_text: str | None = None,
) -> GapDiagnosisReport:
    normalized_text = " ".join(
        [
            startup_profile.description or "",
            startup_profile.ai_usage_summary or "",
            source_text or "",
        ]
    ).lower()
    gaps = [
        gap
        for gap in (
            _diagnose_external_api_dependency(startup_profile),
            _diagnose_inference_latency_cost(assessment),
            _diagnose_model_serving_maturity(assessment, normalized_text),
            _diagnose_agent_governance(startup_profile, assessment),
            _diagnose_data_pipeline_scale(startup_profile, normalized_text),
            _diagnose_voice_ai(startup_profile),
            _diagnose_healthcare_readiness(startup_profile, assessment),
            _diagnose_robotics_simulation(startup_profile),
            _diagnose_cybersecurity_ai(startup_profile),
        )
        if gap is not None
    ]

    return GapDiagnosisReport(gaps=tuple(gaps), summary=_build_summary(gaps))


def _diagnose_with_llm(
    startup_profile: StartupProfileDraft,
    assessment: AiMaturityAssessmentDraft,
    source_text: str,
) -> GapDiagnosisReport:
    settings = get_settings()
    response = generate_openai_json(
        settings=settings,
        system_prompt=(
            "Você é um arquiteto de IA da NVIDIA. Identifique gaps técnicos reais "
            "na stack de IA da startup usando apenas as evidências fornecidas. "
            "Responda em JSON válido, sem markdown."
        ),
        user_prompt=(
            "Retorne JSON no formato: "
            '{"summary": string, "gaps": ['
            '{"gap_type": string, "priority": "high|medium|low", '
            '"confidence": number, "evidence_basis": "evidence_backed|inferred", '
            '"rationale": string, "suggested_action": string}'
            "]}. "
            "Use gap_type curto, como external_api_dependency, inference_latency_or_cost, "
            "model_serving_maturity, agent_governance, data_pipeline_scale, "
            "voice_ai_maturity, healthcare_production_readiness, robotics_or_simulation. "
            f"Startup: {startup_profile.name}\n"
            f"Descrição: {startup_profile.description}\n"
            f"Resumo IA: {startup_profile.ai_usage_summary}\n"
            f"Setores: {', '.join(startup_profile.sectors)}\n"
            f"Sinais: {', '.join(startup_profile.technology_signals)}\n"
            f"Maturidade: {assessment.label}, scores={assessment.scores}\n"
            f"Texto fonte:\n{source_text[:6000]}"
        ),
    )
    gaps = tuple(
        _gap_from_llm(gap)
        for gap in _list_value(response.get("gaps"))
        if isinstance(gap, dict)
    )
    return GapDiagnosisReport(
        gaps=gaps,
        summary=_string_value(response.get("summary")) or _build_summary(list(gaps)),
    )


def _gap_from_llm(raw_gap: dict[str, object]) -> GapDiagnosis:
    return GapDiagnosis(
        gap_type=_string_value(raw_gap.get("gap_type")) or "general_ai_stack_gap",
        priority=_priority_value(raw_gap.get("priority")),
        confidence=_float_between_zero_and_one(raw_gap.get("confidence")),
        evidence_basis=_evidence_basis_value(raw_gap.get("evidence_basis")),
        rationale=_string_value(raw_gap.get("rationale")) or "Gap identificado por LLM.",
        suggested_action=(
            _string_value(raw_gap.get("suggested_action"))
            or "Validar tecnicamente o gap em conversa com a startup."
        ),
    )


def _priority_value(value: object) -> str:
    priority = _string_value(value)
    if priority in {
        RecommendationPriority.HIGH,
        RecommendationPriority.MEDIUM,
        RecommendationPriority.LOW,
    }:
        return priority
    return RecommendationPriority.MEDIUM


def _evidence_basis_value(value: object) -> str:
    basis = _string_value(value)
    if basis in {"evidence_backed", "inferred"}:
        return basis
    return "inferred"


def _string_value(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _list_value(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _float_between_zero_and_one(value: object) -> float:
    if not isinstance(value, int | float):
        return 0.55
    return max(0.0, min(float(value), 1.0))


def _diagnose_external_api_dependency(
    startup_profile: StartupProfileDraft,
) -> GapDiagnosis | None:
    if "External AI API" not in startup_profile.technology_signals:
        return None

    return GapDiagnosis(
        gap_type="external_api_dependency",
        priority=RecommendationPriority.HIGH,
        confidence=0.82,
        evidence_basis="evidence_backed",
        rationale="A startup mostra sinais públicos de dependência de APIs externas de IA.",
        suggested_action=(
            "Comparar NVIDIA NIM ou inferência própria para custo, latência e controle."
        ),
    )


def _diagnose_inference_latency_cost(
    assessment: AiMaturityAssessmentDraft,
) -> GapDiagnosis | None:
    sensitivity = assessment.scores.get("cost_latency_sensitivity", 0)
    if sensitivity <= 0:
        return None

    priority = RecommendationPriority.HIGH if sensitivity >= 0.55 else RecommendationPriority.MEDIUM
    return GapDiagnosis(
        gap_type="inference_latency_or_cost",
        priority=priority,
        confidence=min(0.6 + sensitivity * 0.25, 0.9),
        evidence_basis="evidence_backed",
        rationale="O texto indica pressão de latência, custo, performance ou otimização.",
        suggested_action="Avaliar Triton, TensorRT-LLM, batching e quantização.",
    )


def _diagnose_model_serving_maturity(
    assessment: AiMaturityAssessmentDraft,
    normalized_text: str,
) -> GapDiagnosis | None:
    if assessment.scores.get("ai_workflow_depth", 0) <= 0:
        return None
    if any(term in normalized_text for term in ("triton", "model server", "serving platform")):
        return None

    priority = (
        RecommendationPriority.HIGH
        if assessment.scores.get("production_deployment_maturity", 0) >= 0.55
        else RecommendationPriority.MEDIUM
    )
    return GapDiagnosis(
        gap_type="model_serving_maturity",
        priority=priority,
        confidence=0.64,
        evidence_basis="inferred",
        rationale="Há uso de IA, mas nenhuma stack de serving aparece nas evidências.",
        suggested_action="Discutir arquitetura de inferência em produção com Triton ou NIM.",
    )


def _diagnose_agent_governance(
    startup_profile: StartupProfileDraft,
    assessment: AiMaturityAssessmentDraft,
) -> GapDiagnosis | None:
    if "AI agents" not in startup_profile.technology_signals:
        return None
    if assessment.scores.get("governance_readiness", 0) > 0:
        return None

    return GapDiagnosis(
        gap_type="agent_governance",
        priority=RecommendationPriority.HIGH,
        confidence=0.72,
        evidence_basis="inferred",
        rationale=(
            "A startup usa agentes de IA, mas não há sinal visível de governança "
            "ou guardrails."
        ),
        suggested_action="Avaliar NeMo Guardrails e práticas de teste de comportamento de agentes.",
    )


def _diagnose_data_pipeline_scale(
    startup_profile: StartupProfileDraft,
    normalized_text: str,
) -> GapDiagnosis | None:
    has_data_signal = "Data pipeline" in startup_profile.technology_signals or any(
        term in normalized_text for term in ("analytics", "etl", "large data", "data platform")
    )
    if not has_data_signal:
        return None

    return GapDiagnosis(
        gap_type="data_pipeline_scale",
        priority=RecommendationPriority.MEDIUM,
        confidence=0.66,
        evidence_basis="evidence_backed",
        rationale="A startup mostra sinais de pipeline de dados ou analytics.",
        suggested_action=(
            "Avaliar RAPIDS, cuDF e cuML para processamento de dados acelerado por GPU."
        ),
    )


def _diagnose_voice_ai(startup_profile: StartupProfileDraft) -> GapDiagnosis | None:
    if "Speech AI" not in startup_profile.technology_signals:
        return None

    return GapDiagnosis(
        gap_type="voice_ai_maturity",
        priority=RecommendationPriority.MEDIUM,
        confidence=0.7,
        evidence_basis="evidence_backed",
        rationale="A startup mostra sinais de voz, fala, transcrição, ASR ou TTS.",
        suggested_action="Avaliar NVIDIA Riva e opções de NIM relacionadas a voz.",
    )


def _diagnose_healthcare_readiness(
    startup_profile: StartupProfileDraft,
    assessment: AiMaturityAssessmentDraft,
) -> GapDiagnosis | None:
    if "healthcare" not in startup_profile.sectors:
        return None

    priority = (
        RecommendationPriority.HIGH
        if assessment.scores.get("governance_readiness", 0) == 0
        else RecommendationPriority.MEDIUM
    )
    return GapDiagnosis(
        gap_type="healthcare_production_readiness",
        priority=priority,
        confidence=0.7,
        evidence_basis="evidence_backed",
        rationale=(
            "IA em saúde costuma exigir governança, privacidade e controles de "
            "produção mais fortes."
        ),
        suggested_action="Revisar fit com Clara, MONAI, NeMo Guardrails e AI Enterprise.",
    )


def _diagnose_robotics_simulation(startup_profile: StartupProfileDraft) -> GapDiagnosis | None:
    if "robotics" not in startup_profile.sectors:
        return None

    return GapDiagnosis(
        gap_type="robotics_or_simulation",
        priority=RecommendationPriority.MEDIUM,
        confidence=0.7,
        evidence_basis="evidence_backed",
        rationale="A startup mostra sinais de robótica, autonomia ou simulação.",
        suggested_action="Avaliar Isaac e Omniverse para fluxos de simulação e robótica.",
    )


def _diagnose_cybersecurity_ai(startup_profile: StartupProfileDraft) -> GapDiagnosis | None:
    if "cybersecurity" not in startup_profile.sectors:
        return None

    return GapDiagnosis(
        gap_type="cybersecurity_ai",
        priority=RecommendationPriority.MEDIUM,
        confidence=0.7,
        evidence_basis="evidence_backed",
        rationale="A startup mostra sinais de cibersegurança ou detecção de ameaças.",
        suggested_action="Avaliar NVIDIA Morpheus para acelerar analytics de segurança com IA.",
    )


def _build_summary(gaps: list[GapDiagnosis]) -> str:
    if not gaps:
        return "Nenhum gap material de stack de IA foi detectado nas evidências disponíveis."

    high_priority_count = sum(1 for gap in gaps if gap.priority == RecommendationPriority.HIGH)
    return (
        f"Foram detectados {len(gaps)} gaps de stack de IA, incluindo "
        f"{high_priority_count} gap(s) de alta prioridade."
    )
