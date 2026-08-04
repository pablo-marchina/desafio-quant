"""Classifier Agent — Fase 3.

Classifica uma startup como ai_native, ai_enabled ou non_ai com base
nos chunks do Qdrant, usando um LLM com fallback multi-provedor.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Literal

import asyncpg
from pydantic import BaseModel, Field
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

from ..logging_conf import get_logger
from .llm_providers import classify_with_fallback

logger = get_logger("agents.classifier")

# ---------------------------------------------------------------------------
# Modelo de saída
# ---------------------------------------------------------------------------

class ClassificationResult(BaseModel):
    startup_id: int
    startup_name: str
    classification: Literal["ai_native", "ai_enabled", "non_ai"]
    confidence_score: float = Field(ge=0.0, le=1.0)
    justification: str
    evidence_chunks: list[int]   # índices (1-based) retornados pelo LLM
    provider_used: str
    classification_date: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ---------------------------------------------------------------------------
# Prompt few-shot
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
Você é especialista em classificar startups tecnológicas brasileiras.
Classifique a startup nos chunks abaixo como UMA das três categorias:

- ai_native: Constrói, treina ou fine-tuna modelos de IA próprios. Possui dados proprietários,
  pipeline de ML interna, ou otimização de inferência própria (TensorRT, Triton, etc.).
  Indicadores: "fine-tuning", "modelos in-house", "dados proprietários", "agentes autônomos",
  "treinamento próprio", "inferência otimizada".

- ai_enabled: Usa IA como funcionalidade, porém depende de APIs externas (OpenAI, Anthropic,
  Google AI, etc.) e NÃO desenvolve tecnologia de IA proprietária. É um integrador/wrapper.
  Indicadores: "API da OpenAI", "ChatGPT", "prompt engineering", "integração com LLM",
  "Copilot", "AI embarcada via API".

- non_ai: Não utiliza IA de forma significativa. Software tradicional, marketplace,
  consultoria, automação básica, SaaS sem componente de IA.

Exemplos de saída:

Chunk #1: "Nossa plataforma realiza fine-tuning de LLMs com dados proprietários de saúde."
→ {"classification":"ai_native","confidence_score":0.95,"justification":"Chunk #1 menciona fine-tuning e dados proprietários, características de AI-native.","evidence_chunks":[1]}

Chunk #1: "Integramos a API da OpenAI para gerar respostas automáticas ao suporte."
→ {"classification":"ai_enabled","confidence_score":0.90,"justification":"Chunk #1 indica dependência de API externa (OpenAI), sem desenvolvimento de IA própria.","evidence_chunks":[1]}

Chunk #1: "Somos um marketplace de produtos orgânicos com entrega em 24 horas."
→ {"classification":"non_ai","confidence_score":0.88,"justification":"Nenhum chunk apresenta termos relacionados a IA ou ML.","evidence_chunks":[]}

IMPORTANTE: Retorne APENAS JSON válido no formato:
{"classification":"...","confidence_score":0.0,"justification":"...","evidence_chunks":[]}
Sem markdown. Sem texto antes ou depois do JSON.\
"""


# ---------------------------------------------------------------------------
# Busca de chunks no Qdrant
# ---------------------------------------------------------------------------

async def fetch_startup_chunks(
    qdrant: AsyncQdrantClient,
    startup_id: int,
    max_chunks: int = 10,
) -> list[dict]:
    """Retorna até max_chunks chunks da startup, priorizando has_ai_signals=True."""
    results, _ = await qdrant.scroll(
        collection_name="startup_chunks",
        scroll_filter=Filter(
            must=[FieldCondition(key="startup_id", match=MatchValue(value=startup_id))]
        ),
        limit=200,
        with_payload=True,
        with_vectors=False,
    )

    chunks = []
    for point in results:
        payload = point.payload or {}
        chunks.append({
            "text": payload.get("text", ""),
            "has_ai_signals": bool(payload.get("has_ai_signals", False)),
            "chunk_type": payload.get("chunk_type", "main_text"),
        })

    # Ordena: sinal AI primeiro, depois os demais
    chunks.sort(key=lambda c: (0 if c["has_ai_signals"] else 1))
    return chunks[:max_chunks]


# ---------------------------------------------------------------------------
# Construção do prompt
# ---------------------------------------------------------------------------

def build_user_prompt(chunks: list[dict], startup_name: str) -> str:
    lines = [f"Analise os chunks da startup **{startup_name}** e classifique:\n"]
    for i, chunk in enumerate(chunks, 1):
        signal_tag = " [AI_SIGNAL]" if chunk["has_ai_signals"] else ""
        text_preview = chunk["text"][:400].replace("\n", " ")
        lines.append(f"[Chunk #{i}]{signal_tag} {text_preview}")
    lines.append(
        "\nRetorne APENAS o JSON com classification, confidence_score, justification e evidence_chunks."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Parsing do JSON retornado pelo LLM
# ---------------------------------------------------------------------------

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
_MALFORMED_TAG_RE = re.compile(r"(?:</)+")


def _repair_raw_text(text: str) -> str:
    """Sanitiza artefatos comuns de respostas malformadas de LLM antes do parse."""
    text = _CONTROL_CHARS_RE.sub(" ", text)   # caracteres de controle não imprimíveis
    text = _MALFORMED_TAG_RE.sub(" ", text)   # artefatos tipo </</</  (truncamento/alucinação)
    text = text.replace("\\/", "/")           # escapes desnecessários de barra
    return text


def _close_unbalanced_json(text: str) -> str:
    """Fecha aspas/chaves/colchetes pendentes em JSON aparentemente truncado."""
    stack: list[str] = []
    in_string = False
    escape = False
    for ch in text:
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in "{[":
            stack.append(ch)
        elif ch in "}]" and stack:
            stack.pop()
    if in_string:
        text += '"'
    for opener in reversed(stack):
        text += "}" if opener == "{" else "]"
    return text


def _clean_json(text: str) -> str:
    """Remove markdown, repara artefatos comuns (control chars, tags soltas, escapes
    desnecessários, truncamento) e extrai o primeiro objeto JSON válido da resposta do LLM."""
    original = text
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text)
    text = _repair_raw_text(text.strip())

    # Candidatos, do mais conservador ao mais agressivo
    candidates = [text]
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        candidates.append(match.group(0))
    first_brace = text.find("{")
    if first_brace != -1:
        candidates.append(text[first_brace:])  # cobre JSON truncado sem "}" final

    for candidate in candidates:
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass
        repaired = _close_unbalanced_json(candidate)
        try:
            json.loads(repaired)
            return repaired
        except json.JSONDecodeError:
            continue

    raise ValueError(f"Nenhum JSON válido encontrado na resposta do LLM: {original[:200]!r}")


# ---------------------------------------------------------------------------
# Persistência
# ---------------------------------------------------------------------------

async def save_classification(
    pool: asyncpg.Pool,
    result: ClassificationResult,
    evidence_texts: list[str],
) -> None:
    await pool.execute(
        """
        INSERT INTO classifications
            (startup_id, classification, confidence_score, justification,
             evidence_chunks, provider_used, classification_date)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (startup_id) DO UPDATE SET
            classification      = EXCLUDED.classification,
            confidence_score    = EXCLUDED.confidence_score,
            justification       = EXCLUDED.justification,
            evidence_chunks     = EXCLUDED.evidence_chunks,
            provider_used       = EXCLUDED.provider_used,
            classification_date = EXCLUDED.classification_date
        """,
        result.startup_id,
        result.classification,
        result.confidence_score,
        result.justification,
        evidence_texts,
        result.provider_used,
        result.classification_date.replace(tzinfo=None),  # asyncpg exige naive datetime p/ TIMESTAMP
    )


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

_DEFAULT_NON_AI = ClassificationResult(
    startup_id=0,
    startup_name="",
    classification="non_ai",
    confidence_score=0.0,
    justification="Sem dados suficientes para análise.",
    evidence_chunks=[],
    provider_used="none",
)


async def classify_startup(
    startup_id: int,
    pool: asyncpg.Pool,
    qdrant: AsyncQdrantClient,
    force_provider: str | None = None,
    dry_run: bool = False,
) -> ClassificationResult:
    """Classifica uma startup e opcionalmente persiste no PostgreSQL."""

    # 1. Nome da startup
    row = await pool.fetchrow(
        "SELECT name FROM startups_discovered WHERE id = $1", startup_id
    )
    if not row:
        raise ValueError(f"Startup id={startup_id} não encontrada no banco.")
    startup_name: str = row["name"]
    logger.info("🔍 Classificando startup ID %d (%s)...", startup_id, startup_name)

    # 2. Busca chunks no Qdrant
    chunks = await fetch_startup_chunks(qdrant, startup_id)
    ai_signal_count = sum(1 for c in chunks if c["has_ai_signals"])
    logger.info("📚 Encontrados %d chunks (sinais AI: %d)", len(chunks), ai_signal_count)

    # 3. Sem chunks → non_ai default
    if not chunks:
        logger.warning("Startup %d sem chunks no Qdrant — classificando como non_ai.", startup_id)
        result = _DEFAULT_NON_AI.model_copy(
            update={"startup_id": startup_id, "startup_name": startup_name}
        )
        if not dry_run:
            await save_classification(pool, result, [])
            logger.info("💾 Resultado salvo no PostgreSQL.")
        return result

    # 4. Constrói prompt
    user_prompt = build_user_prompt(chunks, startup_name)

    if dry_run:
        print("\n" + "=" * 60)
        print("SYSTEM PROMPT:")
        print(SYSTEM_PROMPT[:500] + "...")
        print("\nUSER PROMPT:")
        print(user_prompt)
        print("=" * 60)

    # 5. Chama LLM com fallback
    raw_json, provider = await classify_with_fallback(
        SYSTEM_PROMPT, user_prompt, startup_id, force_provider
    )

    if dry_run:
        print("\nRESPOSTA DO LLM:")
        print(raw_json)
        print("=" * 60 + "\n")

    # 6-8. Limpa, parseia, valida e monta o resultado — resiliente a JSON malformado
    try:
        raw_json = _clean_json(raw_json)
        llm_out = json.loads(raw_json)

        # Clamp confidence_score (LLMs menores às vezes retornam > 1.0)
        llm_out["confidence_score"] = max(0.0, min(1.0, float(llm_out.get("confidence_score", 0.0))))

        # Valida classificação
        valid_classes = {"ai_native", "ai_enabled", "non_ai"}
        if llm_out.get("classification") not in valid_classes:
            logger.warning("LLM retornou classe inválida '%s' — usando non_ai.", llm_out.get("classification"))
            llm_out["classification"] = "non_ai"
            llm_out["confidence_score"] = 0.0

        # 7. Mapeia índices → textos reais
        evidence_indices: list[int] = [
            i for i in (llm_out.get("evidence_chunks") or [])
            if isinstance(i, int) and 1 <= i <= len(chunks)
        ]
        evidence_texts = [chunks[i - 1]["text"] for i in evidence_indices]

        # 8. Monta resultado
        result = ClassificationResult(
            startup_id=startup_id,
            startup_name=startup_name,
            classification=llm_out["classification"],
            confidence_score=llm_out["confidence_score"],
            justification=llm_out.get("justification", ""),
            evidence_chunks=evidence_indices,
            provider_used=provider,
        )
    except Exception as exc:
        logger.error(
            "Falha ao parsear resposta do LLM (%s) para startup %d: %s — usando non_ai/confiança 0.0.",
            provider, startup_id, exc,
        )
        result = _DEFAULT_NON_AI.model_copy(update={
            "startup_id": startup_id,
            "startup_name": startup_name,
            "justification": f"Falha ao parsear resposta do LLM ({provider}): {exc}",
            "provider_used": "parse_failed",
        })
        evidence_texts = []

    logger.info(
        "🧠 Classificação: %s (confiança: %.2f) via %s",
        result.classification, result.confidence_score, result.provider_used,
    )

    # 9. Persiste
    if not dry_run:
        await save_classification(pool, result, evidence_texts)
        logger.info("💾 Resultado salvo no PostgreSQL.")

    return result
