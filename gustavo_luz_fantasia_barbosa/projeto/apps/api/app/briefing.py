from __future__ import annotations

from app.schemas.analysis import (
    EvidenceCheck,
    StartupRecommendation,
    StartupSearchPlan,
    StartupSourceSummary,
    StartupStructuredProfile,
)
from app.rag.chunking import chunk_text
from app.rag.ingest import startup_evidence_point_id

MIN_RECOMMENDATION_RETRIEVAL_SCORE = 0.35
MIN_TECHNICAL_REASON_CHARS = 40


def _compact_identifier(value: object) -> str:
    text = str(value or "").strip().lower()
    compact = "".join(character if character.isalnum() else "-" for character in text)
    compact = "-".join(part for part in compact.split("-") if part)
    return compact[:80] or "unknown"


def _source_page_evidence(
    source_pages: list[dict[str, object]] | None,
    *,
    analysis_run_id: str | None = None,
) -> tuple[list[str], list[str], int]:
    evidence_ids: list[str] = []
    source_urls: list[str] = []
    total_characters = 0
    for index, page in enumerate(source_pages or [], start=1):
        source_url = str(page.get("source_url") or "").strip()
        characters = int(page.get("characters") or 0)
        if not source_url or characters <= 0:
            continue
        text = str(page.get("text") or page.get("excerpt") or "")
        chunks = chunk_text(text) if analysis_run_id and len(text) >= 80 else []
        if chunks:
            evidence_ids.extend(
                startup_evidence_point_id(
                    analysis_run_id=analysis_run_id,
                    source_url=source_url,
                    chunk_index=chunk.chunk_index,
                )
                for chunk in chunks[:2]
            )
        else:
            evidence_ids.append(f"startup_page:{index}:{_compact_identifier(source_url)}")
        source_urls.append(source_url)
        total_characters += characters
    return evidence_ids, source_urls, total_characters


def _nvidia_evidence_id(recommendation: StartupRecommendation) -> str | None:
    source_url = str(recommendation.source_url or "").strip()
    if not source_url:
        return None
    return (
        "nvidia_source:"
        f"{_compact_identifier(recommendation.technology)}:"
        f"{_compact_identifier(source_url)}"
    )


def validate_evidence(
    *,
    description: str | None,
    source_summary: StartupSourceSummary | None,
    structured_profile: StartupStructuredProfile | None = None,
    gaps: list[str],
    recommendations: list[StartupRecommendation],
    source_pages: list[dict[str, object]] | None = None,
    min_recommendation_retrieval_score: float = MIN_RECOMMENDATION_RETRIEVAL_SCORE,
    analysis_run_id: str | None = None,
) -> list[EvidenceCheck]:
    checks: list[EvidenceCheck] = []
    has_manual_context = bool(description and description.strip())
    has_collected_source = bool(source_summary and source_summary.status == "collected")
    startup_page_ids, startup_page_urls, startup_page_characters = (
        _source_page_evidence(source_pages, analysis_run_id=analysis_run_id)
    )
    has_public_page_evidence = has_collected_source and bool(startup_page_ids)
    has_startup_evidence = has_manual_context or has_collected_source
    manual_evidence_ids = ["manual_context"] if has_manual_context else []
    startup_source_ids = (
        startup_page_ids
        if startup_page_ids
        else [f"startup_source:{_compact_identifier(source_summary.source_url)}"]
        if has_collected_source and source_summary
        else []
    )
    startup_source_urls = (
        startup_page_urls
        if startup_page_urls
        else [str(source_summary.source_url)]
        if has_collected_source and source_summary
        else []
    )
    if description:
        checks.append(
            EvidenceCheck(
                claim="Perfil inicial informado pelo usuario.",
                support="direct",
                confidence=0.72,
                source="descricao_manual",
                note="A descricao manual foi usada como entrada principal da analise.",
                severity="info",
                claim_type="startup_profile",
                evidence_ids=manual_evidence_ids,
                minimum_required="descricao_manual_ou_fonte_publica",
            )
        )

    if source_summary and source_summary.status == "collected":
        checks.append(
            EvidenceCheck(
                claim="Site publico da empresa foi coletado.",
                support="direct",
                confidence=0.86 if has_public_page_evidence else 0.78,
                source=str(source_summary.source_url),
                note=(
                    f"Foram extraidos {source_summary.characters} caracteres do site "
                    f"informado em {len(startup_page_urls) or 1} pagina(s) e "
                    f"{len(startup_page_ids) or 1} evidencia(s) rastreavel(is)."
                ),
                severity="info",
                claim_type="startup_source",
                evidence_ids=startup_source_ids,
                source_urls=startup_source_urls,
                minimum_required="site_publico_coletado",
            )
        )
    elif source_summary:
        blocks_source = not has_manual_context
        checks.append(
            EvidenceCheck(
                claim="Site publico da empresa nao foi coletado.",
                support="unsupported",
                confidence=0.2,
                source=str(source_summary.source_url),
                note="A analise precisou depender dos campos manuais.",
                severity="warning",
                blocks_recommendation=blocks_source,
                claim_type="startup_source",
                source_urls=[str(source_summary.source_url)],
                minimum_required="descricao_manual_ou_site_publico_coletado",
                blocking_reason=(
                    "Nao ha descricao manual nem fonte publica coletada."
                    if blocks_source
                    else None
                ),
            )
        )
    else:
        blocks_source = not has_manual_context
        checks.append(
            EvidenceCheck(
                claim="Nenhum site publico foi coletado para esta startup.",
                support="unsupported",
                confidence=0.25 if has_manual_context else 0.12,
                source="sistema",
                note=(
                    "As recomendacoes dependem de entrada manual e devem ser tratadas "
                    "como hipotese ate haver fonte publica."
                ),
                severity="warning",
                blocks_recommendation=blocks_source,
                claim_type="startup_source",
                minimum_required="descricao_manual_ou_site_publico_coletado",
                blocking_reason=(
                    "Nao ha descricao manual nem fonte publica coletada."
                    if blocks_source
                    else None
                ),
            )
        )

    if structured_profile:
        profile_fields = (
            ("founders", "Founders ou lideranca identificados."),
            ("funding", "Sinais de funding ou tracao financeira identificados."),
            ("customers", "Clientes, casos ou mercado atendido identificados."),
            ("technologies", "Tecnologias usadas pela startup identificadas."),
            ("ai_signals", "Sinais de uso de IA identificados."),
        )
        for field_name, claim in profile_fields:
            for index, item in enumerate(
                getattr(structured_profile, field_name), start=1
            ):
                source = str(item.source_url or "perfil_extraido")
                is_manual = source == "manual_context"
                checks.append(
                    EvidenceCheck(
                        claim=f"{claim} {item.value}",
                        support="direct" if not is_manual else "manual",
                        confidence=float(item.confidence),
                        source=source,
                        note=item.evidence,
                        severity="info",
                        claim_type=f"profile_{field_name}",
                        evidence_ids=[
                            f"profile:{field_name}:{index}:{_compact_identifier(item.value)}"
                        ],
                        source_urls=[] if is_manual else [source],
                        minimum_required="trecho_manual_ou_fonte_publica_com_keyword",
                    )
                )

    for gap in gaps:
        gap_support = "direct" if has_startup_evidence else "inferred"
        gap_confidence = (
            0.76
            if has_public_page_evidence
            else 0.68
            if has_collected_source
            else 0.58
            if has_manual_context
            else 0.35
        )
        gap_blocks = not has_startup_evidence
        checks.append(
            EvidenceCheck(
                claim=f"Gap tecnico considerado: {gap}.",
                support=gap_support,
                confidence=gap_confidence,
                source="entrada_da_analise",
                note="Gap usado para consultar a base NVIDIA e priorizar recomendacoes.",
                severity="info" if gap_support == "direct" else "warning",
                blocks_recommendation=gap_blocks,
                claim_type="gap",
                evidence_ids=manual_evidence_ids + startup_source_ids,
                source_urls=startup_source_urls,
                minimum_required="gap_informado_com_contexto_da_startup",
                blocking_reason=(
                    "Gap tecnico sem contexto minimo da startup."
                    if gap_blocks
                    else None
                ),
            )
        )

    for recommendation in recommendations:
        has_nvidia_source = bool(str(recommendation.source_url or "").strip())
        retrieval_score = float(recommendation.retrieval_score or 0.0)
        technical_reason_chars = len((recommendation.technical_reason or "").strip())
        evidence_confidence = min(0.9, max(0.32, 0.46 + retrieval_score * 0.38))
        if has_public_page_evidence:
            evidence_confidence = min(0.96, evidence_confidence + 0.1)
        elif has_collected_source:
            evidence_confidence = min(0.92, evidence_confidence + 0.06)
        elif has_manual_context:
            evidence_confidence = min(0.82, evidence_confidence)
        else:
            evidence_confidence = min(evidence_confidence, 0.45)

        blocking_reasons: list[str] = []
        if not has_startup_evidence:
            blocking_reasons.append(
                "falta evidencia publica ou descricao manual da startup"
            )
        if not has_nvidia_source:
            blocking_reasons.append("falta URL da fonte NVIDIA recuperada")
        if retrieval_score < min_recommendation_retrieval_score:
            blocking_reasons.append(
                "score de recuperacao abaixo do piso "
                f"{min_recommendation_retrieval_score:.2f}"
            )
        if technical_reason_chars < MIN_TECHNICAL_REASON_CHARS:
            blocking_reasons.append(
                "trecho tecnico recuperado e curto demais para decisao forte"
            )

        blocks = bool(blocking_reasons)
        if blocks:
            support = "unsupported" if not has_nvidia_source else "weak_retrieval"
        elif has_public_page_evidence:
            support = "direct_and_retrieved"
        elif has_manual_context:
            support = "manual_and_retrieved"
        else:
            support = "retrieved"
        severity = "warning" if blocks or not has_public_page_evidence else "info"
        note = (
            "Recomendacao sustentada por trecho recuperado da base NVIDIA "
            f"com score {retrieval_score:.3f}."
        )
        if startup_page_characters:
            note += f" Evidencia publica da startup soma {startup_page_characters} caracteres."
        elif has_manual_context:
            note += " Evidencia da startup vem de descricao manual."
        if blocking_reasons:
            note += " Bloqueios: " + "; ".join(blocking_reasons) + "."
        nvidia_id = _nvidia_evidence_id(recommendation)
        evidence_ids = manual_evidence_ids + startup_source_ids
        if nvidia_id:
            evidence_ids.append(nvidia_id)
        if analysis_run_id:
            evidence_ids.append(f"analysis_run:{analysis_run_id}")
        checks.append(
            EvidenceCheck(
                claim=f"{recommendation.technology} tem aderencia ao perfil analisado.",
                support=support,
                confidence=evidence_confidence,
                source=str(recommendation.source_url or "sem_fonte"),
                note=note,
                severity=severity,
                blocks_recommendation=blocks,
                claim_type="recommendation",
                evidence_ids=evidence_ids,
                source_urls=(
                    startup_source_urls
                    + ([str(recommendation.source_url)] if has_nvidia_source else [])
                ),
                recommendation_technology=recommendation.technology,
                minimum_required=(
                    "contexto_da_startup + fonte_nvidia + "
                    f"retrieval_score>={min_recommendation_retrieval_score:.2f} + "
                    f"trecho_tecnico>={MIN_TECHNICAL_REASON_CHARS}_chars"
                ),
                blocking_reason=(
                    "; ".join(blocking_reasons) if blocking_reasons else None
                ),
            )
        )

    if not checks:
        checks.append(
            EvidenceCheck(
                claim="Nao ha evidencias suficientes para sustentar uma analise robusta.",
                support="unsupported",
                confidence=0.15,
                source="sistema",
                note="Informe uma descricao ou site publico para melhorar a analise.",
                severity="warning",
                blocks_recommendation=True,
                claim_type="system",
                minimum_required="descricao_manual_ou_site_publico_coletado",
                blocking_reason="Nao ha evidencias para validar a analise.",
            )
        )

    return checks


def _profile_lines(
    title: str,
    items: list[object],
) -> list[str]:
    lines = [f"### {title}"]
    if not items:
        lines.append("- Sem evidencia estruturada nesta execucao.")
        return lines
    for item in items:
        value = getattr(item, "value", "")
        source_url = getattr(item, "source_url", "")
        confidence = float(getattr(item, "confidence", 0.0) or 0.0)
        evidence = getattr(item, "evidence", "")
        lines.append(f"- {value} ({confidence:.2f}) - Fonte: {source_url}")
        if evidence:
            lines.append(f"  Evidencia: {evidence[:260]}")
    return lines


def _approach_playbook_lines(
    *,
    nvidia_fit_score: int,
    wrapper_risk_score: int,
    gaps: list[str],
    recommendations: list[StartupRecommendation],
    quality_metrics: dict[str, object] | None,
) -> list[str]:
    evidence_coverage = float(
        (quality_metrics or {}).get("evidence_coverage_percent", 0) or 0
    )
    top_recommendation = recommendations[0] if recommendations else None
    top_technology = (
        top_recommendation.technology
        if top_recommendation
        else "uma tecnologia NVIDIA ainda a validar"
    )
    main_gap = gaps[0] if gaps else "o principal gargalo tecnico da startup"

    if nvidia_fit_score >= 80 and evidence_coverage >= 60 and recommendations:
        timing = "quente"
        timing_reason = (
            "ha fit NVIDIA alto, recomendacao recuperada e evidencias publicas "
            "suficientes para uma abordagem tecnica inicial."
        )
    elif nvidia_fit_score >= 60 and recommendations:
        timing = "morno"
        timing_reason = (
            "ha sinais de aderencia, mas a conversa deve validar evidencias e "
            "metricas antes de propor uma iniciativa maior."
        )
    else:
        timing = "exploratorio"
        timing_reason = (
            "a prioridade e descobrir contexto tecnico antes de posicionar uma "
            "solucao NVIDIA especifica."
        )

    if wrapper_risk_score >= 65:
        competitive_risk = (
            "alto risco de comoditizacao por dependencia de APIs externas; a "
            "abordagem deve enfatizar controle, custo, latencia e independencia."
        )
    elif wrapper_risk_score >= 40:
        competitive_risk = (
            "risco intermediario; vale investigar se ha dados proprietarios, "
            "workflow profundo e barreiras tecnicas reais."
        )
    else:
        competitive_risk = (
            "risco wrapper baixo; a conversa pode focar escala, confiabilidade, "
            "governanca e aceleracao do roadmap tecnico."
        )

    category = (top_recommendation.category if top_recommendation else "").lower()
    if category == "model_deployment":
        discovery_question = (
            "Qual e hoje o custo por inferencia, a latencia p95 e o plano de "
            "fallback quando o provedor externo falha?"
        )
    elif category in {"data_processing", "data_science"}:
        discovery_question = (
            "Qual pipeline de dados mais limita experimentacao, custo ou tempo de "
            "entrega do produto?"
        )
    elif category == "optimization":
        discovery_question = (
            "Qual decisao operacional poderia ser otimizada com dados reais de "
            "rotas, scheduling, alocacao ou planejamento?"
        )
    elif category in {"speech_ai", "conversational_ai"}:
        discovery_question = (
            "Quais metricas de voz ou atendimento mais pesam hoje: qualidade, "
            "latencia, custo, privacidade ou escala?"
        )
    else:
        discovery_question = (
            "Qual metrica tecnica, se melhorasse nos proximos 30 dias, teria maior "
            "impacto no produto ou na margem?"
        )

    return [
        "## Playbook de abordagem NVIDIA",
        f"- Timing sugerido: **{timing}** - {timing_reason}",
        (
            f"- Hipotese de valor: conectar **{top_technology}** ao gap "
            f"**{main_gap}** com um piloto pequeno e mensuravel."
        ),
        f"- Risco competitivo: {competitive_risk}",
        f"- Pergunta de descoberta: {discovery_question}",
    ]


def generate_briefing_markdown(
    *,
    startup_name: str,
    sector: str | None,
    classification: str,
    ai_native_score: int,
    wrapper_risk_score: int,
    nvidia_fit_score: int,
    source_summary: StartupSourceSummary | None,
    gaps: list[str],
    recommendations: list[StartupRecommendation],
    evidence_checks: list[EvidenceCheck],
    limitations: list[str],
    search_plan: StartupSearchPlan | None = None,
    structured_profile: StartupStructuredProfile | None = None,
    quality_metrics: dict[str, object] | None = None,
    pipeline_trace: list[dict[str, object]] | None = None,
) -> str:
    lines = [
        f"# Briefing executivo - {startup_name}",
        "",
        "## Resumo",
        (
            f"- Classificacao: **{classification}**\n"
            f"- Setor informado: **{sector or 'nao informado'}**\n"
            f"- AI-Native Score: **{ai_native_score}/100**\n"
            f"- Wrapper Risk Score: **{wrapper_risk_score}/100**\n"
            f"- NVIDIA Fit Score: **{nvidia_fit_score}/100**"
        ),
        "",
        "## Fonte analisada",
    ]

    if source_summary:
        lines.extend(
            [
                f"- URL: {source_summary.source_url}",
                f"- Status: {source_summary.status}",
                f"- Caracteres extraidos: {source_summary.characters}",
            ]
        )
        if source_summary.excerpt:
            lines.extend(["", "Trecho inicial:", "", f"> {source_summary.excerpt[:360]}"])
    else:
        lines.append("- Nenhum site publico foi coletado nesta execucao.")

    if search_plan:
        lines.extend(
            [
                "",
                "## Plano de busca",
                f"- Versao: {search_plan.version}",
                f"- Consulta: {search_plan.query}",
                "- Termos: " + ", ".join(search_plan.search_terms),
                "- Fontes priorizadas: " + ", ".join(search_plan.source_priorities),
                "- Alvos de evidencia: " + ", ".join(search_plan.evidence_targets),
            ]
        )

    if structured_profile:
        lines.extend(["", "## Perfil estruturado extraido"])
        lines.extend(_profile_lines("Founders e lideranca", structured_profile.founders))
        lines.extend(_profile_lines("Funding e tracao financeira", structured_profile.funding))
        lines.extend(_profile_lines("Clientes e casos", structured_profile.customers))
        lines.extend(_profile_lines("Tecnologias detectadas", structured_profile.technologies))
        lines.extend(_profile_lines("Sinais de IA", structured_profile.ai_signals))

    lines.extend(["", "## Gaps tecnicos considerados"])
    if gaps:
        lines.extend(f"- {gap}" for gap in gaps)
    else:
        lines.append("- Nenhum gap tecnico foi informado.")

    lines.extend(["", "## Recomendacoes NVIDIA"])
    if recommendations:
        for index, recommendation in enumerate(recommendations, start=1):
            rerank = recommendation.rerank_details or {}
            rerank_provider = rerank.get("provider")
            rerank_line = (
                f"- Reranking: {rerank_provider} "
                f"(vetorial {float(rerank.get('vector_score', 0.0)):.3f}, "
                f"BM25 {float(rerank.get('bm25_score', 0.0)):.3f}, "
                f"lexical {float(rerank.get('lexical_score', 0.0)):.3f}, "
                f"dominio {float(rerank.get('domain_score', 0.0)):.3f})"
                if rerank
                else None
            )
            lines.extend(
                [
                    f"### {index}. {recommendation.technology}",
                    f"- Categoria: {recommendation.category}",
                    f"- Prioridade: {recommendation.priority}",
                    f"- Complexidade de implementacao: {recommendation.implementation_complexity}",
                    f"- Score final de recuperacao: {recommendation.retrieval_score:.3f}",
                    f"- Fonte: {recommendation.source_url}",
                    *( [rerank_line] if rerank_line else [] ),
                    "",
                    "Justificativa tecnica:",
                    "",
                    recommendation.technical_reason,
                    "",
                    "Justificativa de negocio:",
                    "",
                    recommendation.business_reason,
                    "",
                    "Proxima acao:",
                    "",
                    recommendation.next_action
                    or "Validar aderencia tecnica com a equipe da startup.",
                    "",
                ]
            )
    else:
        lines.append("- Nenhuma recomendacao foi recuperada.")

    lines.extend(["## Evidencias e confianca"])
    for check in evidence_checks:
        block_suffix = " Bloqueia decisao forte." if check.blocks_recommendation else ""
        evidence_suffix = (
            f" Evidencias: {', '.join(check.evidence_ids[:4])}."
            if check.evidence_ids
            else ""
        )
        reason_suffix = (
            f" Motivo: {check.blocking_reason}."
            if check.blocking_reason
            else ""
        )
        lines.append(
            f"- **{check.support} / {check.severity}** ({check.confidence:.2f}) - "
            f"{check.claim} Fonte: {check.source}. {check.note}"
            f"{evidence_suffix}{reason_suffix}{block_suffix}"
        )

    if quality_metrics:
        targets = quality_metrics.get("targets") or {}
        lines.extend(
            [
                "",
                "## Metricas de qualidade",
                f"- Fontes publicas rastreaveis: {quality_metrics.get('public_source_pages', 0)}",
                f"- Cobertura de evidencias: {quality_metrics.get('evidence_coverage_percent', 0)}%",
                f"- Groundedness das recomendacoes: {quality_metrics.get('recommendation_groundedness_percent', 0)}%",
                f"- Recomendacoes acionaveis: {quality_metrics.get('actionable_recommendation_percent', 0)}%",
                f"- Latencia estimada da pipeline: {quality_metrics.get('pipeline_latency_ms', 0)} ms",
                "- Metas MVP: "
                + ", ".join(
                    f"{name}={'ok' if value else 'atencao'}"
                    for name, value in targets.items()
                ),
            ]
        )

    lines.extend([""])
    lines.extend(
        _approach_playbook_lines(
            nvidia_fit_score=nvidia_fit_score,
            wrapper_risk_score=wrapper_risk_score,
            gaps=gaps,
            recommendations=recommendations,
            quality_metrics=quality_metrics,
        )
    )

    lines.extend(["", "## Proxima acao sugerida"])
    if recommendations:
        top = recommendations[0]
        lines.append(
            f"- Validar com a startup se o gap principal realmente se conecta a "
            f"{top.technology} e preparar uma conversa tecnica curta usando a fonte "
            f"{top.source_url}. {top.next_action}"
        )
    else:
        lines.append(
            "- Coletar mais evidencias publicas antes de sugerir uma abordagem tecnica."
        )

    lines.extend(["", "## Limitacoes"])
    lines.extend(f"- {limitation}" for limitation in limitations)

    if pipeline_trace:
        lines.extend(["", "## Pipeline executada"])
        for step in pipeline_trace:
            duration = step.get("duration_ms")
            duration_text = f" em {duration} ms" if duration is not None else ""
            lines.append(
                f"- **{step.get('agent')}** / {step.get('name')}: "
                f"{step.get('status')}{duration_text}. {step.get('summary') or ''}"
            )

    return "\n".join(lines).strip() + "\n"
