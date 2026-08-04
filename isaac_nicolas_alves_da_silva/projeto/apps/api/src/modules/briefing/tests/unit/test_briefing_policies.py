"""Testes das regras deterministicas de briefing (domain/policies.py)."""

from apps.api.src.modules.briefing.domain.policies import (
    EvidenceItem,
    RecommendationItem,
    StartupAIProfileItem,
    StartupSummary,
    assess_risks,
    build_briefing_markdown,
    suggest_next_actions,
)

STARTUP = StartupSummary(
    name="Acme AI",
    sector="LLM customer service",
    description="Plataforma de atendimento com LLM.",
    country="BR",
    website_url="https://acme.example.com",
)
EVIDENCE = EvidenceItem(
    title="Acme launches LLM chatbot",
    source_url="https://example.com/news",
    evidence_type="news",
    confidence_score=0.9,
)
RECOMMENDATION = RecommendationItem(
    technology_name="NVIDIA NIM",
    category="model_serving",
    score=0.8,
    confidence=0.8,
    justification="Evidencias mencionam llm e inference.",
    nivel="forte",
    signal_origins=("llm: evidencia acme", "inference: descricao"),
)
AI_PROFILE = StartupAIProfileItem(
    ai_workload_type="nlp",
    model_type="fine_tuning",
    data_modality="text",
    deployment_stage="production",
    infra_environment="cloud",
    gpu_need="high",
    latency_requirement="real_time",
    current_tools=("LangChain", "Postgres"),
    business_goal="reduzir tempo de atendimento",
)


def test_assess_risks_flags_missing_evidence() -> None:
    risks = assess_risks([], [RECOMMENDATION])

    assert any("nenhuma evidencia" in risk.lower() for risk in risks)


def test_assess_risks_flags_missing_recommendations() -> None:
    risks = assess_risks([EVIDENCE], [])

    assert any("aderencia clara" in risk.lower() for risk in risks)


def test_assess_risks_flags_low_confidence_evidence() -> None:
    low_confidence = EvidenceItem(
        title="Vague mention",
        source_url="https://example.com/blog",
        evidence_type="blog",
        confidence_score=0.2,
    )

    risks = assess_risks([low_confidence], [RECOMMENDATION])

    assert any("confiabilidade baixa" in risk.lower() for risk in risks)


def test_assess_risks_empty_when_profile_is_solid() -> None:
    risks = assess_risks([EVIDENCE], [RECOMMENDATION])

    assert risks == []


def test_suggest_next_actions_without_recommendations() -> None:
    actions = suggest_next_actions([])

    assert any("coletar evidencias" in action.lower() for action in actions)


def test_suggest_next_actions_with_top_recommendation() -> None:
    actions = suggest_next_actions([RECOMMENDATION])

    assert actions == ["Agendar conversa tecnica sobre NVIDIA NIM (model_serving)."]


def test_build_briefing_markdown_includes_all_sections() -> None:
    content = build_briefing_markdown(
        startup=STARTUP,
        evidences=[EVIDENCE],
        recommendations=[RECOMMENDATION],
        risks=["Risco de exemplo."],
        next_actions=["Acao de exemplo."],
    )

    assert "# Briefing Executivo - Acme AI" in content
    assert "## Resumo Executivo" in content
    assert "## Tese de Fit NVIDIA" in content
    assert "## Nivel de Confianca Geral" in content
    assert "## O Que Foi Encontrado" in content
    assert "## O Que Nao Foi Encontrado" in content
    assert "## Evidencias Principais" in content
    assert "[Acme launches LLM chatbot](https://example.com/news)" in content
    assert "## Matriz de Recomendacoes" in content
    assert "| NVIDIA NIM | 80% | 80% | forte | medium |" in content
    assert "## Recomendacoes Acionaveis" in content
    assert "NVIDIA NIM" in content
    assert "## Hipoteses a Qualificar" in content
    assert "## O Que Coletar" in content
    assert "## Riscos" in content
    assert "Risco de exemplo." in content
    assert "## Perguntas de Qualificacao" in content
    assert "## Proximas Acoes" in content
    assert "Acao de exemplo." in content


def test_build_briefing_markdown_handles_empty_evidence_and_recommendations() -> None:
    content = build_briefing_markdown(
        startup=STARTUP,
        evidences=[],
        recommendations=[],
        risks=[],
        next_actions=["Coletar mais dados."],
    )

    assert "Nenhuma evidencia aprovada registrada." in content
    assert "Nenhuma recomendacao gerada ainda." in content
    assert "Nenhum sinal estruturado de IA foi extraido ainda." in content
    assert "Nenhum risco identificado." in content


def test_build_briefing_markdown_includes_ai_profile_signals() -> None:
    content = build_briefing_markdown(
        startup=STARTUP,
        evidences=[EVIDENCE],
        recommendations=[RECOMMENDATION],
        risks=[],
        next_actions=["Acao de exemplo."],
        ai_profile=AI_PROFILE,
    )

    assert "Workload de IA: nlp" in content
    assert "Necessidade de GPU: high" in content
    assert "Ferramentas atuais: LangChain, Postgres" in content
    assert "Nenhuma lacuna critica de perfil foi identificada." in content


def test_build_briefing_markdown_includes_ai_profile_field_confidence() -> None:
    profile = StartupAIProfileItem(
        ai_workload_type="analytics",
        data_modality="tabular",
        deployment_stage="production",
        field_confidence={
            "ai_workload_type": 0.88,
            "data_modality": 0.76,
            "deployment_stage": 0.7,
        },
    )

    content = build_briefing_markdown(
        startup=STARTUP,
        evidences=[EVIDENCE],
        recommendations=[RECOMMENDATION],
        risks=[],
        next_actions=["Acao de exemplo."],
        ai_profile=profile,
    )

    assert "Workload de IA: analytics (confianca 88%)" in content
    assert "Modalidade de dados: tabular (confianca 76%)" in content
    assert "Estagio de deploy: production (confianca 70%)" in content


def test_build_briefing_markdown_separates_exploratory_recommendations() -> None:
    exploratory = RecommendationItem(
        technology_name="NVIDIA Riva",
        category="speech_ai",
        score=0.42,
        confidence=0.28,
        justification="Ha sinal inicial de voz.",
        nivel="exploratoria",
        faltando=("evidencias concretas sobre ASR/TTS",),
    )

    content = build_briefing_markdown(
        startup=STARTUP,
        evidences=[EVIDENCE],
        recommendations=[exploratory],
        risks=[],
        next_actions=["Validar voz."],
    )

    assert "## Recomendacoes Acionaveis" in content
    assert "Nenhuma recomendacao forte" in content
    assert "## Hipoteses a Qualificar" in content
    assert "## O Que Coletar" in content
    assert "Para elevar ao nivel de hipotese: evidencias concretas sobre ASR/TTS." in content
    assert "Para NVIDIA Riva: validar evidencias concretas sobre ASR/TTS." in content


def test_build_briefing_markdown_includes_nvidia_context_when_provided() -> None:
    content = build_briefing_markdown(
        startup=STARTUP,
        evidences=[EVIDENCE],
        recommendations=[RECOMMENDATION],
        risks=[],
        next_actions=["Acao de exemplo."],
        nvidia_context=(
            "NVIDIA NIM e NeMo aceleram atendimento via LLM. "
            "Fontes: https://nvidia.com/nim."
        ),
    )

    assert "## Contexto NVIDIA" in content
    assert "NVIDIA NIM e NeMo aceleram atendimento via LLM." in content
    assert content.index("## O Que Coletar") < content.index(
        "## Contexto NVIDIA"
    )
    assert content.index("## Contexto NVIDIA") < content.index("## Riscos")


def test_build_briefing_markdown_omits_nvidia_context_when_absent() -> None:
    content = build_briefing_markdown(
        startup=STARTUP,
        evidences=[EVIDENCE],
        recommendations=[RECOMMENDATION],
        risks=[],
        next_actions=["Acao de exemplo."],
    )

    assert "## Contexto NVIDIA" not in content
