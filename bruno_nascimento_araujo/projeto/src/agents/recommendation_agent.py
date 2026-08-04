"""Recommendation Agent — Fase 3.

Cruza a classificação da startup (Agente 1) com os chunks NVIDIA recuperados via
RAG (Agente 2) e uma camada de heurísticas de negócio para gerar recomendações
técnicas priorizadas, usando um LLM com fallback multi-provedor.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Literal

import asyncpg
from pydantic import BaseModel, Field
from qdrant_client import AsyncQdrantClient

from ..logging_conf import get_logger
from .classifier import _clean_json
from .llm_providers import classify_with_fallback
from .rag_agent import RAGChunkResult, run_rag

logger = get_logger("agents.recommendation")

TOP_K_CHUNKS = 5


# ---------------------------------------------------------------------------
# Modelos de saída
# ---------------------------------------------------------------------------

class Recommendation(BaseModel):
    tech_name: str
    category: str
    priority: Literal["alta", "media", "baixa"]
    technical_justification: str
    business_justification: str
    implementation_complexity: Literal["baixa", "media", "alta"]
    next_actions: list[str]
    evidence_chunks: list[int]  # posições (1-based) na lista de chunks do prompt


class RecommendationResult(BaseModel):
    startup_id: int
    startup_name: str
    classification: str
    recommendations: list[Recommendation]
    heuristic_suggestions: str  # rastreabilidade das regras aplicadas (join das strings)
    provider_used: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Camada de heurísticas (regras de negócio)
# ---------------------------------------------------------------------------

def generate_heuristic_suggestions(classification: str, sector: str, description: str) -> list[str]:
    suggestions: list[str] = []
    sector = sector or ""
    description = (description or "").lower()

    if classification == "ai_native" and sector in ["Fintech", "Financeiro", "Pagamentos", "Bancos"]:
        suggestions.append(
            "Priorize NVIDIA NeMo para governança de agentes de IA em transações "
            "financeiras e NVIDIA AI Enterprise para infraestrutura escalável."
        )
        suggestions.append("Considere NVIDIA Triton para otimização de inferência em tempo real.")

    if classification == "ai_native" and sector in ["Saúde", "Healthtech", "Life Sciences", "Biotech"]:
        suggestions.append("Priorize NVIDIA Clara e MONAI para healthcare e análise de imagens médicas.")
        suggestions.append("Considere NVIDIA NeMo Guardrails para segurança e compliance em dados sensíveis.")

    if classification == "ai_native" and sector in ["Robótica", "Automação", "Indústria 4.0", "AgTech"]:
        suggestions.append("Priorize NVIDIA Isaac e Omniverse para simulação e robótica.")
        suggestions.append("Considere NVIDIA Triton para inferência em borda (edge inference).")

    if classification == "ai_enabled" and any(t in description for t in ["latência", "tempo de resposta", "baixa latência"]):
        suggestions.append("Priorize NVIDIA Triton e TensorRT-LLM para otimização de inferência e redução de latência.")

    if classification == "ai_enabled" and any(t in description for t in ["dados", "analytics", "processamento"]):
        suggestions.append("Considere NVIDIA RAPIDS, cuDF e cuML para aceleração de pipelines de dados com GPU.")

    if classification == "ai_enabled" and any(t in description for t in ["voz", "call center", "transcrição"]):
        suggestions.append("Priorize NVIDIA Riva para ASR, TTS e modelos de voz.")

    if classification == "non_ai":
        suggestions.append("Recomende NVIDIA Inception para capacitação, acesso a créditos de GPU e suporte técnico.")

    if classification in ["ai_native", "ai_enabled"]:
        suggestions.append("Avaliar NVIDIA AI Enterprise para gerenciamento de infraestrutura de IA em produção.")
        suggestions.append("Considerar treinamento com NVIDIA Deep Learning Institute (DLI) para capacitação da equipe técnica.")

    return suggestions


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
Você é um arquiteto de soluções de IA da NVIDIA. Gere recomendações técnicas \
priorizadas para a startup descrita pelo usuário.

Instruções:
1. Baseie-se fortemente nas "Dicas do Sistema" (se houver) e cruze com os dados dos chunks.
2. Para cada recomendação, defina:
   - tech_name: Nome da tecnologia (ex: "NVIDIA Triton Inference Server")
   - category: Categoria (ex: "Inferência", "Modelos", "Dados")
   - priority: "alta", "media" ou "baixa"
   - technical_justification: Por que essa tecnologia resolve o gap identificado.
   - business_justification: Impacto em custo, performance ou time-to-market.
   - implementation_complexity: "baixa", "media" ou "alta"
   - next_actions: Lista de ações sugeridas (ex: "Agendar demo", "Ativar créditos Inception")
   - evidence_chunks: Lista de IDs (números) dos chunks usados como evidência (ex: [1, 3])
3. CRITÉRIO DE EVIDÊNCIA (OBRIGATÓRIO): Os chunks listados em evidence_chunks DEVEM \
mencionar explicitamente a tecnologia recomendada ou o problema específico que ela resolve.
   - Exemplo válido: se recomendar "NVIDIA Triton", o chunk deve mencionar "Triton", \
"inferência", ou "latência".
   - Exemplo inválido: usar um chunk sobre "RAPIDS" para justificar "Inception" — a menos \
que o chunk mencione explicitamente o programa Inception.
   - Se nenhum chunk contiver evidência literal para a recomendação, mantenha evidence_chunks: [].
4. Use os números entre colchetes dos chunks (ex: [Chunk 1]) para o campo evidence_chunks.
5. Retorne APENAS um JSON válido, sem markdown, no formato:
{"recommendations": [{"tech_name": "...", "category": "...", "priority": "...", \
"technical_justification": "...", "business_justification": "...", \
"implementation_complexity": "...", "next_actions": ["..."], "evidence_chunks": [1]}]}\
"""


def _format_chunks(chunks: list[RAGChunkResult]) -> str:
    if not chunks:
        return "(nenhum chunk recuperado do Banco de Conhecimento NVIDIA)"
    lines = []
    for i, c in enumerate(chunks, 1):
        preview = c.text[:400].replace("\n", " ")
        lines.append(f"[Chunk {i}] {c.tech_name} ({c.category}): {preview}")
    return "\n".join(lines)


def build_user_prompt(
    name: str, sector: str, classification: str, confidence: float,
    justification: str, heuristic_suggestions: str, chunks: list[RAGChunkResult],
) -> str:
    return (
        f"Startup: {name}\n"
        f"Setor: {sector}\n"
        f"Classificação: {classification} (Confiança: {confidence:.2f})\n"
        f"Justificativa da Classificação: {justification}\n"
        f"Dicas do Sistema (Heurísticas): {heuristic_suggestions}\n\n"
        f"Tecnologias NVIDIA recuperadas do Banco de Conhecimento (numeradas):\n"
        f"{_format_chunks(chunks)}\n\n"
        f"Retorne APENAS o JSON com a chave 'recommendations'."
    )


# ---------------------------------------------------------------------------
# Fallback puro-heurística (quando todos os LLMs falham)
# ---------------------------------------------------------------------------

def _heuristic_only_recommendations(suggestions: list[str]) -> list[Recommendation]:
    return [
        Recommendation(
            tech_name=s.split(" para ")[0].replace("Priorize ", "").replace("Considere ", "")[:80],
            category="Heurística",
            priority="media",
            technical_justification=f"Gerado por regra de negócio (LLM indisponível): {s}",
            business_justification="Baseado em regras de setor/classificação; requer validação humana.",
            implementation_complexity="media",
            next_actions=["Revisar manualmente com um especialista NVIDIA."],
            evidence_chunks=[],
        )
        for s in suggestions
    ]


# ---------------------------------------------------------------------------
# Persistência
# ---------------------------------------------------------------------------

async def save_recommendations(pool: asyncpg.Pool, result: RecommendationResult) -> None:
    await pool.execute(
        """
        INSERT INTO recommendations (startup_id, classification, heuristic_suggestions, recommendations, generated_at)
        VALUES ($1, $2, $3, $4::jsonb, $5)
        ON CONFLICT (startup_id) DO UPDATE SET
            classification        = EXCLUDED.classification,
            heuristic_suggestions = EXCLUDED.heuristic_suggestions,
            recommendations       = EXCLUDED.recommendations,
            generated_at          = EXCLUDED.generated_at
        """,
        result.startup_id,
        result.classification,
        result.heuristic_suggestions,
        json.dumps([r.model_dump() for r in result.recommendations], ensure_ascii=False),
        result.generated_at.replace(tzinfo=None),
    )


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

async def generate_recommendations(
    startup_id: int,
    pool: asyncpg.Pool,
    qdrant: AsyncQdrantClient,
    force_provider: str | None = None,
    dry_run: bool = False,
) -> RecommendationResult:
    """Gera (e opcionalmente persiste) recomendações para uma startup."""

    # 1. Startup + classificação
    row = await pool.fetchrow(
        """
        SELECT sd.name, sd.sector, c.classification, c.confidence_score, c.justification
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
    name, sector, classification = row["name"], row["sector"] or "", row["classification"]
    confidence, justification = row["confidence_score"], row["justification"]
    logger.info("📊 Gerando recomendações para startup ID %d (%s)...", startup_id, name)
    logger.info("🧠 Classificação: %s (confiança: %.2f)", classification, confidence)

    # 2. Heurísticas
    suggestions = generate_heuristic_suggestions(classification, sector, justification)
    heuristic_str = "\n".join(suggestions) if suggestions else "Nenhuma heurística aplicável."
    logger.info("⚙️ Heurísticas aplicadas: %s", heuristic_str)

    # 3. RAG — só para ai_native/ai_enabled (non_ai usa só heurísticas + LLM)
    top_chunks: list[RAGChunkResult] = []
    if classification in ("ai_native", "ai_enabled"):
        try:
            rag_result = await run_rag(
                startup_id=startup_id, query=None, top_k=TOP_K_CHUNKS,
                category_filter=None, pool=pool, qdrant=qdrant, dry_run=dry_run,
            )
            top_chunks = rag_result.top_chunks
            logger.info("📚 Recuperados %d chunks da NVIDIA via RAG Agent.", len(top_chunks))
        except Exception as exc:
            logger.error("RAG Agent falhou para startup %d: %s — seguindo só com heurísticas.", startup_id, exc)
            top_chunks = []
    else:
        logger.info("⏭️ Startup non_ai — pulando RAG (recomendação via heurísticas + prompt simples).")

    # 4. Prompt + LLM (fallback: recomendações só-heurística se todos os LLMs falharem)
    user_prompt = build_user_prompt(name, sector, classification, confidence, justification, heuristic_str, top_chunks)

    if dry_run:
        print("\n" + "=" * 60 + "\nSYSTEM PROMPT:\n" + SYSTEM_PROMPT[:500] + "...")
        print("\nUSER PROMPT:\n" + user_prompt + "\n" + "=" * 60)

    provider = "heuristics_only"
    recommendations: list[Recommendation] = []
    try:
        raw_json, provider = await classify_with_fallback(SYSTEM_PROMPT, user_prompt, startup_id, force_provider)
        if dry_run:
            print("\nRESPOSTA DO LLM:\n" + raw_json + "\n" + "=" * 60 + "\n")
        raw_json = _clean_json(raw_json)
        llm_out = json.loads(raw_json)

        for rec_raw in llm_out.get("recommendations", []):
            rec_raw["priority"] = rec_raw.get("priority") if rec_raw.get("priority") in ("alta", "media", "baixa") else "media"
            rec_raw["implementation_complexity"] = (
                rec_raw.get("implementation_complexity")
                if rec_raw.get("implementation_complexity") in ("baixa", "media", "alta") else "media"
            )
            rec_raw["evidence_chunks"] = [
                i for i in (rec_raw.get("evidence_chunks") or [])
                if isinstance(i, int) and 1 <= i <= len(top_chunks)
            ]
            recommendations.append(Recommendation(**rec_raw))

        logger.info("🤖 Gerando recomendações com %s...", provider)
    except Exception as exc:
        logger.error("Todos os LLMs falharam para startup %d: %s — usando só heurísticas.", startup_id, exc)
        recommendations = _heuristic_only_recommendations(suggestions)
        provider = "heuristics_only"

    result = RecommendationResult(
        startup_id=startup_id, startup_name=name, classification=classification,
        recommendations=recommendations, heuristic_suggestions=heuristic_str, provider_used=provider,
    )

    logger.info("✅ %d recomendações geradas.", len(recommendations))

    if not dry_run:
        await save_recommendations(pool, result)
        logger.info("💾 Recomendações salvas no PostgreSQL.")

    return result
