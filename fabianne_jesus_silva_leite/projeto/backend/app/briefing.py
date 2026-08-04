from datetime import datetime, timezone

from app.rag.schemas import (
    BriefingResponse,
    FlightPlanPhase,
    FlightPlanResponse,
    RecommendationResponse,
    ResearchWithNvidiaContextResponse,
)


MAX_QUOTE_CHARS = 500


def shorten_quote(text: str) -> str:
    cleaned_text = " ".join(text.split())
    cleaned_text = cleaned_text.replace('\\"', '"')
    cleaned_text = cleaned_text.replace("”", '"')
    cleaned_text = cleaned_text.replace("“", '"')

    if len(cleaned_text) <= MAX_QUOTE_CHARS:
        return cleaned_text

    return f"{cleaned_text[:MAX_QUOTE_CHARS].rstrip()}..."


def format_evidences(evidences) -> list[str]:
    lines = []
    seen_ids = set()

    for evidence in evidences:
        if evidence.evidence_id in seen_ids:
            continue

        seen_ids.add(evidence.evidence_id)

        lines.append(
            f'- **{evidence.evidence_id}** - '
            f'[{evidence.source_url}]({evidence.source_url})\n'
            f'  > {shorten_quote(evidence.quote)}'
        )

    return lines


def build_recommendation_section(
    recommendation,
    position: int,
) -> str:
    startup_evidence_lines = format_evidences(
        recommendation.startup_evidences,
    )

    nvidia_evidence_lines = format_evidences(
        recommendation.nvidia_evidences,
    )

    lines = [
        f"### {position}. {recommendation.technology_name}",
        "",
        f"**Prioridade:** {recommendation.priority}",
        f"**Complexidade:** {recommendation.complexity}",
        "",
        "**Justificativa técnica**",
        recommendation.technical_reason,
        "",
        "**Justificativa de negócio**",
        recommendation.business_reason,
        "",
        "**Próxima ação**",
        recommendation.next_action,
        "",
        "**Evidências da startup**",
        *startup_evidence_lines,
        "",
        "**Evidências NVIDIA**",
        *nvidia_evidence_lines,
        "",
    ]

    return "\n".join(lines)


def unique_recommended_technologies(
    recommendation_response: RecommendationResponse,
) -> list[str]:
    technologies = []

    for recommendation in recommendation_response.recommendations:
        if recommendation.technology_name not in technologies:
            technologies.append(recommendation.technology_name)

    return technologies


def build_flight_plan(
    recommendation_response: RecommendationResponse,
) -> FlightPlanResponse:
    technologies = unique_recommended_technologies(
        recommendation_response,
    )

    primary_technology = (
        technologies[0]
        if technologies
        else "a tecnologia NVIDIA priorizada"
    )

    implementation_technologies = technologies or [
        "Tecnologias NVIDIA recomendadas",
    ]

    return FlightPlanResponse(
        summary=(
            "Plano de 90 dias para validar uma hipótese técnica, "
            "executar um piloto controlado e decidir os próximos "
            "passos com base em evidências."
        ),
        phases=[
            FlightPlanPhase(
                period="0-30 dias",
                title="Diagnóstico e desenho do piloto",
                objective=(
                    "Transformar a recomendação prioritária em um "
                    "escopo de piloto mensurável."
                ),
                actions=[
                    (
                        "Alinhar com a startup o workflow prioritário "
                        f"para avaliação com {primary_technology}."
                    ),
                    (
                        "Definir métricas de baseline para qualidade, "
                        "latência, throughput, custo e segurança."
                    ),
                    (
                        "Mapear integrações, dados disponíveis, "
                        "restrições de segurança e responsáveis técnicos."
                    ),
                ],
                nvidia_technologies=[primary_technology],
                success_criteria=[
                    "Escopo do piloto aprovado pelas partes técnicas.",
                    "Baseline e métricas de sucesso documentados.",
                    "Dados, integrações e riscos iniciais mapeados.",
                ],
            ),
            FlightPlanPhase(
                period="31-60 dias",
                title="Implementação e validação técnica",
                objective=(
                    "Construir uma prova de valor controlada e medir "
                    "o ganho em relação ao baseline."
                ),
                actions=[
                    (
                        "Implementar o fluxo de piloto em ambiente "
                        "controlado com dados e integrações acordados."
                    ),
                    (
                        "Configurar observabilidade para qualidade, "
                        "latência, throughput, falhas e uso de recursos."
                    ),
                    (
                        "Executar testes de carga, segurança e cenário "
                        "real de uso antes de qualquer expansão."
                    ),
                ],
                nvidia_technologies=implementation_technologies,
                success_criteria=[
                    "Fluxo prioritário funcionando em ambiente controlado.",
                    "Métricas comparáveis ao baseline coletadas.",
                    "Riscos técnicos e operacionais registrados.",
                ],
            ),
            FlightPlanPhase(
                period="61-90 dias",
                title="Avaliação, escala e próximo ciclo",
                objective=(
                    "Decidir entre expansão, ajustes adicionais ou "
                    "novo ciclo de validação com base nos resultados."
                ),
                actions=[
                    (
                        "Comparar os resultados do piloto com os critérios "
                        "de sucesso definidos no início."
                    ),
                    (
                        "Priorizar melhorias de arquitetura, desempenho, "
                        "governança ou experiência conforme as evidências."
                    ),
                    (
                        "Definir plano de rollout, responsáveis, custos e "
                        "próximo checkpoint técnico-comercial."
                    ),
                ],
                nvidia_technologies=implementation_technologies,
                success_criteria=[
                    "Decisão documentada sobre expansão ou novo ciclo.",
                    "Plano de rollout com responsáveis e métricas definido.",
                    "Próximos passos técnicos e comerciais priorizados.",
                ],
            ),
        ],
    )


def build_flight_plan_markdown(
    flight_plan: FlightPlanResponse,
) -> list[str]:
    lines = [
        "## 5. NVIDIA Flight Plan - 90 dias",
        "",
        flight_plan.summary,
        "",
    ]

    for phase in flight_plan.phases:
        lines.extend(
            [
                f"### {phase.period} - {phase.title}",
                "",
                f"**Objetivo:** {phase.objective}",
                "",
                "**Ações**",
                *[f"- {action}" for action in phase.actions],
                "",
                "**Tecnologias NVIDIA relacionadas**",
                *[
                    f"- {technology}"
                    for technology in phase.nvidia_technologies
                ],
                "",
                "**Critérios de sucesso**",
                *[
                    f"- {criterion}"
                    for criterion in phase.success_criteria
                ],
                "",
            ],
        )

    return lines


def build_briefing_markdown(
    research_with_context: ResearchWithNvidiaContextResponse,
    recommendation_response: RecommendationResponse,
    flight_plan: FlightPlanResponse,
) -> str:
    research = research_with_context.research
    classification = research.classification

    lines = [
        f"# Startup Briefing - {research.startup_name}",
        "",
        (
            "Relatório gerado a partir de fontes públicas, "
            "evidências validadas e documentação oficial NVIDIA."
        ),
        "",
        "## 1. Resumo executivo",
        "",
        f"- **Classificação:** {classification.category}",
        f"- **AI-native score:** {classification.ai_native_score}",
        f"- **Wrapper risk score:** {classification.wrapper_risk_score}",
        (
            "- **NVIDIA opportunity score:** "
            f"{classification.nvidia_opportunity_score}"
        ),
        (
            "- **Fontes públicas coletadas com sucesso:** "
            f"{research.sources_successful}"
        ),
        "",
        "## 2. Perfil público identificado",
        "",
        (
            "- Evidências de IA no produto: "
            f"{len(research.profile.ai_product)}"
        ),
        (
            "- Evidências de workflow operacional: "
            f"{len(research.profile.workflow_depth)}"
        ),
        (
            "- Evidências de dados proprietários ou internos: "
            f"{len(research.profile.proprietary_data)}"
        ),
        (
            "- Evidências de governança e segurança: "
            f"{len(research.profile.governance_security)}"
        ),
        (
            "- Evidências de escala e tração: "
            f"{len(research.profile.scale_traction)}"
        ),
        "",
        "## 3. Gaps e limites públicos",
        "",
    ]

    if research.gaps:
        for gap in research.gaps:
            lines.append(f"- **{gap.category}:** {gap.message}")
    else:
        lines.append(
            "- Não foram identificados gaps públicos relevantes "
            "pelas regras atuais."
        )

    lines.extend(
        [
            "",
            "## 4. Tecnologias NVIDIA recomendadas",
            "",
        ],
    )

    for position, recommendation in enumerate(
        recommendation_response.recommendations,
        start=1,
    ):
        lines.append(
            build_recommendation_section(
                recommendation=recommendation,
                position=position,
            ),
        )

    lines.extend(build_flight_plan_markdown(flight_plan))

    lines.extend(
        [
            "## 6. Limitações da análise",
            "",
        ],
    )

    if recommendation_response.limitations:
        for limitation in recommendation_response.limitations:
            lines.append(f"- {limitation}")
    else:
        lines.append(
            "- A análise considera somente informações públicas "
            "e evidências recuperadas no momento da consulta."
        )

    lines.extend(
        [
            "",
            "## 7. Próximos passos sugeridos",
            "",
            "1. Validar as hipóteses técnicas com a startup.",
            (
                "2. Priorizar um assessment ou piloto para a "
                "recomendação de maior prioridade."
            ),
            (
                "3. Confirmar requisitos de infraestrutura, dados, "
                "segurança, custo e integração."
            ),
            (
                "4. Registrar novas evidências antes de avançar "
                "para uma recomendação comercial definitiva."
            ),
        ],
    )

    return "\n".join(lines)


def build_briefing(
    research_with_context: ResearchWithNvidiaContextResponse,
    recommendation_response: RecommendationResponse,
) -> BriefingResponse:
    flight_plan = build_flight_plan(recommendation_response)

    return BriefingResponse(
        startup_name=research_with_context.research.startup_name,
        generated_at=datetime.now(timezone.utc),
        recommendation_count=len(
            recommendation_response.recommendations,
        ),
        markdown=build_briefing_markdown(
            research_with_context=research_with_context,
            recommendation_response=recommendation_response,
            flight_plan=flight_plan,
        ),
        flight_plan=flight_plan,
    )