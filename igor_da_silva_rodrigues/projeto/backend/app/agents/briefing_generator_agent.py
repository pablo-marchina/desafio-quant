from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from app.core.contracts import validate_contract
from app.core.schemas import BriefingGeneratorInput


class BriefingGeneratorAgent:
    """Render validated pipeline artifacts as a concise executive Markdown briefing."""

    def __init__(self, now: Callable[[], datetime] | None = None) -> None:
        self.now = now or (lambda: datetime.now(UTC))

    def generate(self, payload: BriefingGeneratorInput | dict[str, Any]) -> str:
        data = validate_contract(BriefingGeneratorInput, payload)
        profile = data.startup_profile
        maturity = data.classificacao_ia
        refined = data.recomendacao_refinada.recomendacao_refinada
        impact = data.estimativa_impacto
        date = self.now().date().isoformat()
        name = maturity.startup
        location = _location(profile)
        evidence_summary, evidence_sources = _evidence_summary(data.validacao_evidencias)
        sources = _all_sources(evidence_sources, impact, data.inception_fit)

        lines = [
            f"# Briefing NVIDIA Inception - {name}",
            "",
            f"**Data:** {date}  ",
            f"**Responsavel:** {_clean(data.responsavel)}",
            "",
            "## 1. Resumo Executivo",
            _summary(profile, maturity, refined.fit_score, impact.indice_impacto_agregado),
            "",
            "## 2. Perfil da Startup",
            f"- **Site:** {_clean(profile.get('site_oficial') or profile.get('site') or 'Nao informado')}",
            f"- **Categoria:** {_clean(profile.get('categoria') or 'Nao informada')}",
            f"- **Localizacao:** {location}",
            f"- **Descricao:** {_sourced_description(profile)}",
            f"- **Maturidade de IA:** {maturity.classificacao}, nivel {maturity.nivel_maturidade}/5, "
            f"confianca {maturity.confianca_classificacao:.0%}",
            f"- **Evidencias:** {evidence_summary}",
            "",
            "## 3. Aderencia ao NVIDIA Inception",
        ]
        lines.extend(_inception_fit_lines(data.inception_fit))
        lines.extend(["", "## 4. Diagnostico Tecnico"])
        needs = maturity.necessidades_limitacoes or ["Nenhuma limitacao confirmada nas evidencias."]
        lines.extend(f"- {_clean(item)}" for item in needs[:5])
        lines.append(
            "- Oportunidade NVIDIA: validar as tecnologias recomendadas em provas de conceito "
            "com baseline, criterio de aceite e fonte documental."
        )
        lines.extend(["", "## 5. Recomendacao NVIDIA", "", _recommendation_table(refined), ""])
        lines.extend(["## 6. Roadmap Sugerido"])
        lines.extend(_roadmap_lines(refined.roadmap))
        lines.extend(["", "## 7. Impacto Estimado"])
        lines.extend(_impact_lines(impact))
        lines.extend(["", "## 8. Proximas Acoes"])
        lines.extend(_next_actions(refined.perguntas_startup, refined.tecnologias_priorizadas))
        lines.extend(["", "## 9. Apendice: Evidencias-Chave"])
        lines.extend(f"- {source}" for source in sources[:10])
        if not sources:
            lines.append("- Nenhuma URL de evidencia disponivel; confirmar fontes antes do contato.")
        if impact.incertezas:
            lines.extend(["", "**Incertezas:** " + " ".join(_clean(item) for item in impact.incertezas[:3])])
        return "\n".join(lines).strip() + "\n"


def gerar_briefing_executivo(
    payload: BriefingGeneratorInput | dict[str, Any],
    now: Callable[[], datetime] | None = None,
) -> str:
    return BriefingGeneratorAgent(now=now).generate(payload)


def _summary(profile: dict[str, Any], maturity: Any, fit: float, impact_index: int) -> str:
    category = _clean(profile.get("categoria") or "setor nao informado")
    needs = maturity.necessidades_limitacoes
    challenge = _clean(needs[0]) if needs else "validar prioridades tecnicas"
    return (
        f"{maturity.startup} atua em {category} e foi classificada como {maturity.classificacao} "
        f"no nivel {maturity.nivel_maturidade}/5. O principal ponto a confirmar e {challenge}. "
        f"A recomendacao NVIDIA apresenta fit {fit:.0%} e indice interno de impacto "
        f"{impact_index}/100, condicionado a provas de conceito e baselines da startup."
    )


def _location(profile: dict[str, Any]) -> str:
    parts = [profile.get("cidade"), profile.get("estado"), profile.get("pais")]
    return ", ".join(_clean(part) for part in parts if part) or "Nao informada"


def _sourced_description(profile: dict[str, Any]) -> str:
    description = _clean(profile.get("descricao_curta") or "Nao informada")
    if any(char.isdigit() for char in description) and "%" in description:
        source = _clean(profile.get("site_oficial") or profile.get("site") or "")
        if source:
            return f"{description} [Fonte declarada pela startup]({source})"
        return description + " *(alegacao quantitativa sem fonte confirmada)*"
    return description


def _evidence_summary(validation: Any | None) -> tuple[str, list[str]]:
    if validation is None:
        return "Resumo de validacao nao fornecido.", []
    high = validation.evidencias_validadas
    medium = validation.evidencias_medias
    quality = validation.resumo_consolidado.nota_geral_qualidade_evidencias
    summary = f"{len(high)} alta(s), {len(medium)} media(s), qualidade geral {quality:.0%}."
    return summary, [item.url for item in high + medium]


def _inception_fit_lines(fit: Any | None) -> list[str]:
    if fit is None:
        return [
            "- **Elegibilidade:** unknown. Diagnostico de aderencia nao executado.",
            "- **Proximo passo:** confirmar os criterios oficiais diretamente com a startup.",
        ]
    lines = [
        f"- **Elegibilidade:** {fit.eligibility_status}. {_clean(fit.eligibility_justification)}",
        f"- **Estagio:** {fit.startup_stage}. {_clean(fit.stage_justification)}",
    ]
    identified = [item.need for item in fit.needs if item.status == "identified"]
    lines.append(
        "- **Necessidades identificadas:** "
        + (", ".join(identified) if identified else "nenhuma confirmada nas evidencias")
        + "."
    )
    for match in fit.benefit_matches[:3]:
        lines.append(
            f"- **Beneficio {match.match_status}:** {_clean(match.benefit)}. "
            f"{_clean(match.justification)}"
        )
    if fit.open_questions:
        lines.append("- **Lacuna a confirmar:** " + _clean(fit.open_questions[0]))
    return lines


def _recommendation_table(refined: Any) -> str:
    rows = [
        "| Tecnologia | Fase | Beneficio principal | Complexidade |",
        "|---|---|---|---|",
    ]
    for item in refined.tecnologias_priorizadas:
        rows.append(
            f"| {_cell(item.tecnologia)} | {_cell(_phase_label(item.fase))} | "
            f"{_cell(item.beneficio)} | {_cell(item.complexidade.title())} |"
        )
    if not refined.tecnologias_priorizadas:
        rows.append("| Sem recomendacao fundamentada | - | Validar novas evidencias | - |")
    return "\n".join(rows)


def _roadmap_lines(roadmap: Mapping[Any, Any]) -> list[str]:
    labels = {
        "curto_prazo": "Curto prazo (1-3 meses)",
        "medio_prazo": "Medio prazo (3-6 meses)",
        "longo_prazo": "Longo prazo (6-12 meses)",
    }
    lines = []
    for key, label in labels.items():
        phase = roadmap[key]
        technologies = ", ".join(phase.tecnologias) or "nenhuma tecnologia priorizada"
        actions = "; ".join(_clean(item) for item in phase.acoes) or "reavaliar apos a fase anterior"
        lines.append(f"- **{label}:** {technologies}. {actions}")
    return lines


def _impact_lines(impact: Any) -> list[str]:
    lines = [f"- **Indice de impacto agregado:** {impact.indice_impacto_agregado}/100"]
    for estimate in impact.estimativas_impacto[:5]:
        technical = estimate.impacto_tecnico
        lines.append(
            f"- **{estimate.tecnologia}:** latencia: {_clean(technical.latencia)} "
            f"Vazao: {_clean(technical.vazao)} Custo: {_clean(technical.custo)}"
        )
    if impact.kpis_sugeridos:
        lines.append("- **KPIs:** " + ", ".join(_clean(item) for item in impact.kpis_sugeridos[:8]))
    return lines


def _next_actions(questions: list[str], technologies: list[Any]) -> list[str]:
    lines = ["1. Agendar reuniao com CTO ou founders para validar baselines e prioridades."]
    if technologies:
        lines.append(
            "2. Compartilhar a documentacao oficial das tecnologias priorizadas: "
            + ", ".join(item.tecnologia for item in technologies[:3])
            + "."
        )
        lines.append("3. Definir uma prova de conceito com metrica, responsavel e prazo.")
    else:
        lines.append("2. Coletar evidencias tecnicas adicionais antes de recomendar uma stack.")
        lines.append("3. Reprocessar a recomendacao apos a coleta complementar.")
    if questions:
        lines.append("4. Pergunta de descoberta: " + _clean(questions[0]))
    return lines


def _all_sources(evidence_sources: list[str], impact: Any, inception_fit: Any | None) -> list[str]:
    sources = list(evidence_sources)
    for estimate in impact.estimativas_impacto:
        sources.extend(estimate.fontes_evidencia)
    if inception_fit:
        for match in inception_fit.benefit_matches:
            sources.extend(match.source_urls)
    return list(dict.fromkeys(sources))


def _phase_label(value: str) -> str:
    return value.replace("_", " ").title()


def _clean(value: Any) -> str:
    return " ".join(str(value).split())


def _cell(value: Any) -> str:
    return _clean(value).replace("|", "\\|")[:420]
