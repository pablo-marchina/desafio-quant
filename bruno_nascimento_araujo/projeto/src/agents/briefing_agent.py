"""Briefing Agent — Fase 3 (Agente 4).

Consolida classificação (Agente 1), evidências e recomendações (Agente 3) de uma
startup em um relatório executivo em Markdown. Abordagem híbrida: resumo
executivo gerado por LLM (fallback multi-provedor), resto renderizado por
template Python determinístico.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import asyncpg
from pydantic import BaseModel, Field
from qdrant_client import AsyncQdrantClient

from ..logging_conf import get_logger
from .classifier import fetch_startup_chunks
from .llm_providers import generate_text_with_fallback
from .recommendation_agent import Recommendation

logger = get_logger("agents.briefing")

REPORTS_DIR = "reports"
FALLBACK_SUMMARY = (
    "Resumo executivo não disponível. Consulte as seções abaixo para detalhes "
    "da classificação e recomendações."
)


class BriefingResult(BaseModel):
    startup_id: int
    startup_name: str
    report_markdown: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Resumo executivo (LLM)
# ---------------------------------------------------------------------------

EXEC_SUMMARY_SYSTEM_PROMPT = """\
Você é um redator executivo da NVIDIA. Com base nas informações fornecidas, \
escreva um resumo executivo de 1 parágrafo (máx. 100 palavras) sobre a startup, \
sua classificação e as principais recomendações técnicas. O resumo deve ser \
conciso, profissional e direcionado a um gerente de negócios da NVIDIA Inception. \
Responda apenas com o parágrafo, sem markdown, sem título.\
"""


def _recommendations_summary(recommendations: list[Recommendation]) -> str:
    if not recommendations:
        return "Nenhuma recomendação técnica disponível."
    return "; ".join(f"{r.tech_name} ({r.priority})" for r in recommendations[:5])


async def _generate_exec_summary(
    name: str, sector: str, classification: str, justification: str,
    recommendations: list[Recommendation],
) -> tuple[str, str]:
    user_prompt = (
        f"Startup: {name}\n"
        f"Setor: {sector}\n"
        f"Classificação: {classification}\n"
        f"Justificativa: {justification}\n"
        f"Resumo das Recomendações: {_recommendations_summary(recommendations)}"
    )
    try:
        summary, provider = await generate_text_with_fallback(
            EXEC_SUMMARY_SYSTEM_PROMPT, user_prompt, context_label=f"briefing_{name}"
        )
        return summary.strip(), provider
    except Exception as exc:
        logger.error("Falha ao gerar resumo executivo: %s — usando fallback genérico.", exc)
        return FALLBACK_SUMMARY, "fallback"


# ---------------------------------------------------------------------------
# Template Markdown (determinístico)
# ---------------------------------------------------------------------------

_PRIORITY_LABELS = {"alta": "Alta Prioridade", "media": "Média Prioridade", "baixa": "Baixa Prioridade"}


def _group_by_priority(recommendations: list[Recommendation]) -> dict[str, list[Recommendation]]:
    grouped: dict[str, list[Recommendation]] = {"alta": [], "media": [], "baixa": []}
    for r in recommendations:
        grouped.setdefault(r.priority, []).append(r)
    return grouped


def _render_recommendations_section(recommendations: list[Recommendation]) -> str:
    if not recommendations:
        return "Nenhuma recomendação disponível."
    grouped = _group_by_priority(recommendations)
    parts = []
    for level in ("alta", "media", "baixa"):
        items = grouped.get(level, [])
        if not items:
            continue
        parts.append(f"### {_PRIORITY_LABELS[level]}")
        for r in items:
            actions = ", ".join(r.next_actions) if r.next_actions else "—"
            parts.append(
                f"- **{r.tech_name}** ({r.category})\n"
                f"  *Justificativa Técnica:* {r.technical_justification}\n"
                f"  *Justificativa de Negócio:* {r.business_justification}\n"
                f"  *Complexidade:* {r.implementation_complexity}\n"
                f"  *Próximas Ações:* {actions}"
            )
    return "\n\n".join(parts)


def _render_evidence_section(evidence: list[str]) -> str:
    if not evidence:
        return "Nenhuma evidência textual disponível."
    return "\n".join(f"- {e[:300].replace(chr(10), ' ')}" for e in evidence)


def _collect_next_steps(recommendations: list[Recommendation]) -> list[str]:
    if not recommendations:
        return ["Agendar reunião de descoberta com a equipe NVIDIA Inception."]
    grouped = _group_by_priority(recommendations)
    steps: list[str] = []
    for level in ("alta", "media", "baixa"):
        for r in grouped.get(level, []):
            for action in r.next_actions:
                if action not in steps:
                    steps.append(action)
    return steps[:5] or ["Agendar reunião de descoberta com a equipe NVIDIA Inception."]


def render_markdown(
    name: str, sector: str, website: str, classification: str, confidence: float,
    justification: str, evidence: list[str], recommendations: list[Recommendation],
    exec_summary: str, generated_at: datetime,
) -> str:
    next_steps = "\n".join(f"{i}. {s}" for i, s in enumerate(_collect_next_steps(recommendations), 1))
    return f"""# Relatório Executivo – {name}

**Setor:** {sector or "N/D"}
**Site:** {website or "N/D"}
**Data de Geração:** {generated_at.strftime("%Y-%m-%d %H:%M UTC")}

---

## Resumo Executivo

{exec_summary}

---

## Classificação

**Categoria:** {classification} (Confiança: {confidence:.2f})
**Justificativa:** {justification}

**Evidências utilizadas:**
{_render_evidence_section(evidence)}

---

## Recomendações Técnicas

{_render_recommendations_section(recommendations)}

---

## Próximos Passos para o Time NVIDIA

{next_steps}

---

**Relatório gerado automaticamente pelo NVIDIA Startup AI Radar.**
"""


# ---------------------------------------------------------------------------
# Persistência / exportação
# ---------------------------------------------------------------------------

async def save_briefing(pool: asyncpg.Pool, result: BriefingResult) -> None:
    await pool.execute(
        """
        INSERT INTO briefings (startup_id, report_markdown, generated_at)
        VALUES ($1, $2, $3)
        ON CONFLICT (startup_id) DO UPDATE SET
            report_markdown = EXCLUDED.report_markdown,
            generated_at    = EXCLUDED.generated_at
        """,
        result.startup_id, result.report_markdown, result.generated_at.replace(tzinfo=None),
    )


def _safe_filename(startup_id: int, name: str) -> str:
    slug = "".join(c if c.isalnum() else "_" for c in name).strip("_")
    return f"{startup_id}_{slug}.md"


def export_briefing_file(startup_id: int, name: str, markdown: str) -> str:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    filepath = Path(REPORTS_DIR) / _safe_filename(startup_id, name)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(markdown)
    return str(filepath)


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

async def generate_briefing(
    startup_id: int,
    pool: asyncpg.Pool,
    qdrant: AsyncQdrantClient,
    dry_run: bool = False,
    export_file: bool = False,
) -> BriefingResult:
    """Gera (e opcionalmente persiste/exporta) o briefing executivo de uma startup."""

    # 1. Startup + classificação
    row = await pool.fetchrow(
        """
        SELECT sd.name, sd.sector, sd.official_website,
               c.classification, c.confidence_score, c.justification, c.evidence_chunks
        FROM startups_discovered sd
        JOIN classifications c ON c.startup_id = sd.id
        WHERE sd.id = $1
        """,
        startup_id,
    )
    if not row:
        raise ValueError(
            f"Startup {startup_id} não encontrada ou ainda não classificada. "
            "Rode classify_startup.py primeiro."
        )
    name, sector, website = row["name"], row["sector"] or "", row["official_website"] or ""
    classification, confidence = row["classification"], row["confidence_score"]
    justification = row["justification"]
    logger.info("📄 Gerando briefing para startup ID %d (%s)...", startup_id, name)
    logger.info("🧠 Classificação: %s (confiança: %.2f)", classification, confidence)

    # 2. Evidências — já persistidas como texto; fallback via Qdrant se vazio
    evidence: list[str] = list(row["evidence_chunks"] or [])
    if not evidence:
        chunks = await fetch_startup_chunks(qdrant, startup_id, max_chunks=5)
        evidence = [c["text"] for c in chunks if c["has_ai_signals"]][:5]

    # 3. Recomendações
    reco_row = await pool.fetchrow(
        "SELECT recommendations FROM recommendations WHERE startup_id = $1", startup_id
    )
    recommendations: list[Recommendation] = []
    if reco_row:
        raw_list = json.loads(reco_row["recommendations"])
        recommendations = [Recommendation(**r) for r in raw_list]
        logger.info("📚 %d recomendações encontradas.", len(recommendations))
    else:
        logger.warning("Startup %d sem recomendações — briefing só com classificação/evidências.", startup_id)

    # 4. Resumo executivo (LLM com fallback)
    exec_summary, provider = await _generate_exec_summary(name, sector, classification, justification, recommendations)
    logger.info("✍️ Resumo executivo gerado com %s.", provider)

    # 5. Renderiza Markdown
    generated_at = datetime.now(timezone.utc)
    markdown = render_markdown(
        name, sector, website, classification, confidence, justification,
        evidence, recommendations, exec_summary, generated_at,
    )
    result = BriefingResult(startup_id=startup_id, startup_name=name, report_markdown=markdown, generated_at=generated_at)

    if dry_run:
        print("\n" + "=" * 60)
        print(markdown)
        print("=" * 60 + "\n")
        return result

    await save_briefing(pool, result)
    logger.info("💾 Briefing salvo no PostgreSQL.")

    if export_file:
        path = export_briefing_file(startup_id, name, markdown)
        logger.info("💾 Briefing exportado para %s.", path)

    return result
