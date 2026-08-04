"""Regras deterministicas de avaliacao e montagem do briefing executivo."""

from dataclasses import dataclass

LOW_CONFIDENCE_THRESHOLD = 0.5
LOW_SCORE_THRESHOLD = 0.5


@dataclass(frozen=True)
class StartupSummary:
    name: str
    sector: str | None
    description: str | None
    country: str | None
    website_url: str | None


@dataclass(frozen=True)
class StartupAIProfileItem:
    """Perfil estruturado de IA usado pelo briefing analitico."""

    ai_workload_type: str = "unknown"
    model_type: str = "unknown"
    data_modality: str = "unknown"
    deployment_stage: str = "unknown"
    infra_environment: str = "unknown"
    gpu_need: str = "unknown"
    latency_requirement: str = "unknown"
    scale_signal: str | None = None
    current_tools: tuple[str, ...] = ()
    business_goal: str | None = None
    field_confidence: dict[str, float] | None = None
    field_evidence_ids: dict[str, list[str]] | None = None


@dataclass(frozen=True)
class EvidenceItem:
    title: str | None
    source_url: str
    evidence_type: str
    confidence_score: float | None


@dataclass(frozen=True)
class RecommendationItem:
    technology_name: str
    category: str
    score: float
    justification: str
    confidence: float = 0.0
    complexity: str = "medium"
    nivel: str = "exploratoria"
    faltando: tuple[str, ...] = ()
    signal_origins: tuple[str, ...] = ()
    missing_signals: tuple[str, ...] = ()


def assess_risks(
    evidences: list[EvidenceItem],
    recommendations: list[RecommendationItem],
) -> list[str]:
    """Aponta lacunas no perfil/recomendacoes que o leitor deveria saber."""

    risks: list[str] = []

    if not evidences:
        risks.append(
            "Nenhuma evidencia aprovada associada a esta startup; perfil "
            "pouco fundamentado."
        )
    elif any(
        evidence.confidence_score is not None
        and evidence.confidence_score < LOW_CONFIDENCE_THRESHOLD
        for evidence in evidences
    ):
        risks.append(
            "Pelo menos uma evidencia tem confiabilidade baixa "
            f"(confidence_score < {LOW_CONFIDENCE_THRESHOLD})."
        )

    if not recommendations:
        risks.append(
            "Nenhuma tecnologia NVIDIA com aderencia clara identificada com "
            "as evidencias atuais."
        )
    elif recommendations[0].score < LOW_SCORE_THRESHOLD:
        risks.append(
            "Aderencia da melhor recomendacao ainda e moderada "
            f"(score {recommendations[0].score})."
        )

    return risks


def suggest_next_actions(recommendations: list[RecommendationItem]) -> list[str]:
    """Sugere a proxima acao concreta com base na melhor recomendacao."""

    if not recommendations:
        return [
            "Coletar evidencias adicionais sobre o uso de IA da startup "
            "para habilitar recomendacoes."
        ]

    top = recommendations[0]
    if top.score < LOW_SCORE_THRESHOLD or top.confidence < LOW_CONFIDENCE_THRESHOLD:
        return [
            "Validar em conversa se ha workloads reais de GPU, inferencia, "
            "treinamento ou operacao de IA antes de propor implementacao NVIDIA."
        ]
    return [f"Agendar conversa tecnica sobre {top.technology_name} ({top.category})."]


def _recommendation_strength(recommendation: RecommendationItem) -> str:
    if recommendation.nivel in {
        "forte", "moderada", "exploratoria", "hipotese_prioritaria"
    }:
        return recommendation.nivel
    if recommendation.score >= 0.65 and recommendation.confidence >= 0.65:
        return "forte"
    if (
        recommendation.score >= LOW_SCORE_THRESHOLD
        and recommendation.confidence >= LOW_CONFIDENCE_THRESHOLD
    ):
        return "moderada"
    return "exploratoria"


def _best_recommendation_summary(recommendations: list[RecommendationItem]) -> str:
    if not recommendations:
        return (
            "As evidencias atuais ainda nao sustentam uma recomendacao NVIDIA "
            "prioritaria."
        )

    top = recommendations[0]
    strength = _recommendation_strength(top)
    return (
        f"Melhor sinal atual: {top.technology_name} ({strength}, "
        f"fit {top.score:.0%}, confianca {top.confidence:.0%})."
    )


def _recommendation_context(
    recommendation: RecommendationItem,
    strength: str,
) -> str:
    return (
        f"Leitura: {strength}; fit {recommendation.score:.0%}; "
        f"confianca {recommendation.confidence:.0%}; "
        f"complexidade {recommendation.complexity}."
    )


def _unknown(value: str | None) -> bool:
    return value is None or value.strip().lower() in {"", "unknown", "desconhecida"}


def _confidence_suffix(
    field_confidence: dict[str, float] | None,
    field_name: str,
) -> str:
    if not field_confidence or field_name not in field_confidence:
        return ""
    return f" (confianca {field_confidence[field_name]:.0%})"


def _profile_found_items(ai_profile: StartupAIProfileItem | None) -> list[str]:
    if ai_profile is None:
        return []

    confidence = ai_profile.field_confidence or {}
    fields = [
        ("Workload de IA", "ai_workload_type", ai_profile.ai_workload_type),
        ("Tipo de modelo", "model_type", ai_profile.model_type),
        ("Modalidade de dados", "data_modality", ai_profile.data_modality),
        ("Estagio de deploy", "deployment_stage", ai_profile.deployment_stage),
        ("Ambiente de infra", "infra_environment", ai_profile.infra_environment),
        ("Necessidade de GPU", "gpu_need", ai_profile.gpu_need),
        ("Latencia", "latency_requirement", ai_profile.latency_requirement),
    ]
    items = [
        f"{label}: {value}{_confidence_suffix(confidence, field_name)}"
        for label, field_name, value in fields
        if not _unknown(value)
    ]
    if ai_profile.scale_signal:
        items.append(
            "Sinal de escala: "
            f"{ai_profile.scale_signal}{_confidence_suffix(confidence, 'scale_signal')}"
        )
    if ai_profile.current_tools:
        items.append(
            "Ferramentas atuais: "
            f"{', '.join(ai_profile.current_tools)}"
            f"{_confidence_suffix(confidence, 'current_tools')}"
        )
    if ai_profile.business_goal:
        items.append(
            "Objetivo de negocio: "
            f"{ai_profile.business_goal}"
            f"{_confidence_suffix(confidence, 'business_goal')}"
        )
    return items


def _profile_missing_items(ai_profile: StartupAIProfileItem | None) -> list[str]:
    if ai_profile is None:
        return [
            "perfil estruturado de IA ainda nao extraido",
            "workload, maturidade tecnica e necessidade de GPU desconhecidos",
        ]

    fields = [
        ("workload de IA", ai_profile.ai_workload_type),
        ("tipo de modelo", ai_profile.model_type),
        ("modalidade de dados", ai_profile.data_modality),
        ("estagio de deploy", ai_profile.deployment_stage),
        ("ambiente de infraestrutura", ai_profile.infra_environment),
        ("necessidade de GPU", ai_profile.gpu_need),
        ("requisito de latencia", ai_profile.latency_requirement),
    ]
    missing = [label for label, value in fields if _unknown(value)]
    if not ai_profile.business_goal:
        missing.append("objetivo de negocio")
    if not ai_profile.current_tools:
        missing.append("stack/ferramentas atuais")
    return missing


def _overall_confidence(recommendations: list[RecommendationItem]) -> tuple[str, str]:
    if not recommendations:
        return ("baixo", "nao ha recomendacoes sustentadas pelas evidencias atuais")

    avg = sum(r.confidence for r in recommendations) / len(recommendations)
    strong_count = sum(1 for r in recommendations if _recommendation_strength(r) == "forte")
    if avg >= 0.65 and strong_count > 0:
        return ("alto", "ha recomendacao forte com confianca media adequada")
    if avg >= 0.35:
        return (
            "medio",
            "ha sinais uteis, mas parte das recomendacoes ainda depende de validacao",
        )
    return (
        "baixo",
        "as recomendacoes sao exploratorias ou dependem de evidencias melhores",
    )


def _qualification_questions(
    *,
    ai_profile: StartupAIProfileItem | None,
    recommendations: list[RecommendationItem],
) -> list[str]:
    questions: list[str] = []
    missing = _profile_missing_items(ai_profile)

    if "workload de IA" in missing:
        questions.append(
            "Qual e o workload principal de IA hoje: NLP, visao, fala, "
            "analytics, simulacao ou outro?"
        )
    if "necessidade de GPU" in missing:
        questions.append(
            "Existe gargalo atual de custo, latencia ou throughput que "
            "justificaria aceleracao por GPU?"
        )
    if "estagio de deploy" in missing:
        questions.append("A solucao esta em pesquisa, MVP, piloto, producao ou escala?")
    for recommendation in recommendations:
        if recommendation.faltando:
            questions.append(
                f"Para {recommendation.technology_name}: validar "
                f"{recommendation.faltando[0]}."
            )

    if not questions:
        questions.append(
            "Confirmar com o time tecnico quais workloads entrariam primeiro "
            "em uma prova de valor NVIDIA."
        )
    return questions[:5]


def build_briefing_markdown(
    *,
    startup: StartupSummary,
    evidences: list[EvidenceItem],
    recommendations: list[RecommendationItem],
    risks: list[str],
    next_actions: list[str],
    ai_profile: StartupAIProfileItem | None = None,
    nvidia_context: str | None = None,
) -> str:
    """Monta o briefing executivo analitico em Markdown.

    A funcao continua pura: recebe perfil, evidencias, recomendacoes e contexto
    ja buscados pelo caso de uso; nao faz rede nem banco.
    """

    confidence_label, confidence_reason = _overall_confidence(recommendations)
    found_items = _profile_found_items(ai_profile)
    missing_items = _profile_missing_items(ai_profile)
    strong_recommendations = [
        r for r in recommendations if _recommendation_strength(r) == "forte"
    ]
    hipotese_recommendations = [
        r for r in recommendations
        if _recommendation_strength(r) == "hipotese_prioritaria"
    ]
    exploratory_recommendations = [
        r for r in recommendations
        if _recommendation_strength(r) not in {"forte", "hipotese_prioritaria"}
    ]

    lines = [f"# Briefing Executivo - {startup.name}", "", "## Resumo Executivo"]

    summary_parts = [part for part in (startup.sector, startup.country) if part]
    if summary_parts:
        lines.append(" | ".join(summary_parts))
    if startup.description:
        lines.append(startup.description)
    if startup.website_url:
        lines.append(f"Site: {startup.website_url}")

    lines += ["", "## Tese de Fit NVIDIA"]
    lines.append(_best_recommendation_summary(recommendations))
    top_strength = _recommendation_strength(recommendations[0]) if recommendations else None
    if top_strength == "exploratoria":
        lines.append(
            "A recomendacao deve ser tratada como hipotese de qualificacao, "
            "nao como indicacao tecnica fechada."
        )
    elif top_strength == "hipotese_prioritaria":
        lines.append(
            "Fit relevante identificado mas evidencias insuficientes — "
            "priorizar coleta de dados antes de proposta tecnica."
        )

    lines += ["", "## Nivel de Confianca Geral"]
    lines.append(f"{confidence_label}: {confidence_reason}.")

    lines += ["", "## O Que Foi Encontrado"]
    if found_items:
        lines += [f"- {item}" for item in found_items]
    else:
        lines.append("- Nenhum sinal estruturado de IA foi extraido ainda.")

    lines += ["", "## O Que Nao Foi Encontrado"]
    if missing_items:
        lines += [f"- {item}" for item in missing_items]
    else:
        lines.append("- Nenhuma lacuna critica de perfil foi identificada.")

    lines += ["", "## Evidencias Principais"]
    if evidences:
        for evidence in evidences:
            label = evidence.title or evidence.source_url
            lines.append(f"- [{label}]({evidence.source_url}) - {evidence.evidence_type}")
    else:
        lines.append("- Nenhuma evidencia aprovada registrada.")

    lines += ["", "## Matriz de Recomendacoes"]
    if recommendations:
        lines.append("| Tecnologia | Fit | Confianca | Nivel | Complexidade |")
        lines.append("|---|---:|---:|---|---|")
        for recommendation in recommendations:
            strength = _recommendation_strength(recommendation)
            lines.append(
                f"| {recommendation.technology_name} | "
                f"{recommendation.score:.0%} | "
                f"{recommendation.confidence:.0%} | "
                f"{strength} | {recommendation.complexity} |"
            )
    else:
        lines.append("- Nenhuma recomendacao gerada ainda.")

    lines += ["", "## Recomendacoes Acionaveis"]
    if strong_recommendations:
        for recommendation in strong_recommendations:
            origins = (
                "; ".join(recommendation.signal_origins)
                or "sinais consolidados no motor de recomendacao"
            )
            lines.append(
                f"- **{recommendation.technology_name}**: "
                f"{_recommendation_context(recommendation, 'forte')} "
                f"{recommendation.justification} Sinais: {origins}."
            )
    else:
        lines.append("- Nenhuma recomendacao forte com as evidencias atuais.")

    lines += ["", "## Hipoteses a Qualificar"]
    if hipotese_recommendations:
        for recommendation in hipotese_recommendations:
            faltando = (
                "; ".join(recommendation.faltando)
                or "evidencias concretas sobre uso e maturidade da tecnologia"
            )
            lines.append(
                f"- **{recommendation.technology_name}** (hipotese prioritaria — "
                f"fit relevante, evidencias insuficientes): "
                f"{recommendation.justification} Para confirmar: {faltando}."
            )
    else:
        lines.append("- Nenhuma hipotese prioritaria identificada.")

    lines += ["", "## O Que Coletar"]
    if exploratory_recommendations:
        for recommendation in exploratory_recommendations:
            faltando = (
                "; ".join(recommendation.faltando)
                or "mais evidencias sobre o workload e maturidade tecnica"
            )
            lines.append(
                f"- **{recommendation.technology_name}**: "
                f"Para elevar ao nivel de hipotese: {faltando}."
            )
    else:
        lines.append("- Nenhuma recomendacao exploratoria adicional.")

    if nvidia_context:
        lines += ["", "## Contexto NVIDIA", nvidia_context]

    lines += ["", "## Riscos"]
    if risks:
        lines += [f"- {risk}" for risk in risks]
    else:
        lines.append("- Nenhum risco identificado.")

    lines += ["", "## Perguntas de Qualificacao"]
    lines += [
        f"- {question}"
        for question in _qualification_questions(
            ai_profile=ai_profile,
            recommendations=recommendations,
        )
    ]

    lines += ["", "## Proximas Acoes"]
    lines += [f"- {action}" for action in next_actions]

    return "\n".join(lines).strip() + "\n"
