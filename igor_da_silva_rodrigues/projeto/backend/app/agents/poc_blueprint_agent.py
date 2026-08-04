from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class POCWorkstream(BaseModel):
    technology: str
    phase: str
    objective: str
    prerequisites: list[str] = Field(default_factory=list)
    kpis: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class POCBlueprint(BaseModel):
    startup: str
    purpose: str
    baseline_checklist: list[str]
    workstreams: list[POCWorkstream]
    timeline: list[dict[str, str]]
    uncertainties: list[str]
    markdown: str


class POCBlueprintAgent:
    """Turn grounded recommendations into a measurable, non-promissory POC plan."""

    def generate(
        self,
        startup: str,
        refinement: dict[str, Any] | None,
        impact: dict[str, Any] | None,
    ) -> dict[str, Any]:
        refined = ((refinement or {}).get("refinement_json") or {}).get(
            "recomendacao_refinada", {}
        )
        impact_data = (impact or {}).get("impact_json") or {}
        impact_by_technology = {
            item.get("tecnologia"): item
            for item in impact_data.get("estimativas_impacto") or []
            if isinstance(item, dict)
        }
        suggested_kpis = [str(value) for value in impact_data.get("kpis_sugeridos") or []]
        workstreams = []
        for item in refined.get("tecnologias_priorizadas") or []:
            technology = str(item.get("tecnologia") or "Tecnologia NVIDIA")
            estimate = impact_by_technology.get(technology) or {}
            sources = list(
                dict.fromkeys(
                    [str(value) for value in item.get("fontes_evidencia") or []]
                    + [str(value) for value in estimate.get("fontes_evidencia") or []]
                )
            )
            workstreams.append(
                POCWorkstream(
                    technology=technology,
                    phase=str(item.get("fase") or "curto_prazo"),
                    objective=str(item.get("problema_resolvido") or "Validar aderência técnica."),
                    prerequisites=[str(value) for value in item.get("dependencias") or []],
                    kpis=suggested_kpis,
                    acceptance_criteria=[
                        "Baseline medido antes da alteração e registrado com a mesma carga de teste.",
                        "Resultado reproduzível em pelo menos três execuções controladas.",
                        "Nenhuma regressão nos requisitos de qualidade, segurança e disponibilidade.",
                        "Decisão go/no-go documentada com custo, ganho medido e risco residual.",
                    ],
                    risks=[str(item.get("riscos"))] if item.get("riscos") else [],
                    sources=sources,
                )
            )
        blueprint = POCBlueprint(
            startup=startup,
            purpose=(
                "Validar a stack NVIDIA recomendada contra o baseline real da startup, "
                "sem assumir ganhos antes da medição."
            ),
            baseline_checklist=[
                "Volume e perfil da carga de produção",
                "Latência p50, p95 e p99",
                "Vazão e concorrência",
                "Custo por unidade processada",
                "Qualidade do modelo e taxa de erro",
                "Disponibilidade, segurança e observabilidade",
            ],
            workstreams=workstreams,
            timeline=[
                {"phase": "Semana 1", "activity": "Baseline, dados, ambiente e critérios de aceite"},
                {"phase": "Semanas 2-3", "activity": "Implementação controlada e instrumentação"},
                {"phase": "Semana 4", "activity": "Benchmark, análise de custo e decisão go/no-go"},
            ],
            uncertainties=[str(value) for value in impact_data.get("incertezas") or []],
            markdown="",
        )
        blueprint.markdown = _render_markdown(blueprint)
        return blueprint.model_dump(mode="json")


def _render_markdown(blueprint: POCBlueprint) -> str:
    lines = [
        f"# NVIDIA POC Blueprint - {blueprint.startup}",
        "",
        blueprint.purpose,
        "",
        "## Baseline obrigatório",
    ]
    lines.extend(f"- {item}" for item in blueprint.baseline_checklist)
    for workstream in blueprint.workstreams:
        lines.extend(
            [
                "",
                f"## {workstream.technology}",
                f"- **Fase:** {workstream.phase.replace('_', ' ').title()}",
                f"- **Objetivo:** {workstream.objective}",
                "- **Pré-requisitos:** " + (", ".join(workstream.prerequisites) or "A confirmar"),
                "- **KPIs:** " + (", ".join(workstream.kpis) or "Definir com a startup"),
                "- **Critérios de aceite:**",
            ]
        )
        lines.extend(f"  - {item}" for item in workstream.acceptance_criteria)
        if workstream.sources:
            lines.append("- **Fontes oficiais:**")
            lines.extend(f"  - {source}" for source in workstream.sources)
    lines.extend(["", "## Cronograma"])
    lines.extend(f"- **{item['phase']}:** {item['activity']}" for item in blueprint.timeline)
    if blueprint.uncertainties:
        lines.extend(["", "## Incertezas"])
        lines.extend(f"- {item}" for item in blueprint.uncertainties)
    return "\n".join(lines).strip() + "\n"
