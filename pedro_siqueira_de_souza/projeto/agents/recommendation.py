"""Recommendation Agent — oitava estação do grafo (catálogo de regras + LLM).

Mudança de paradigma (Entregável 4, escolha do gestor):
  ANTES: "fit" era só a similaridade semântica do perfil com os docs NVIDIA (o
  rerank do Cohere) — media parecença de texto, não benefício, e saía baixo para
  todo mundo. AGORA: um CATÁLOGO estruturado de produtos NVIDIA (recommender/
  catalog.py) pontua, por REGRA, o fit de cada produto com cada empresa a partir
  de sinais de necessidade + setor + maturidade. O rerank do RAG entra como UM
  insumo de apoio, não como juiz.

Híbrido regras + LLM:
  - As REGRAS decidem QUAIS produtos e com QUE fit (0–100) — transparente,
    determinístico, auditável (a lição do Entregável 4: regras primeiro).
  - O LLM escreve só o "COMO este produto ajuda ESTA empresa a crescer" sobre os
    produtos que a regra elegeu. É narrativa por cima de fatos, não decisão.
  - RESILIENTE: se o LLM falhar, cai na tese template do próprio catálogo (cada
    produto traz uma) — o pipeline nunca quebra por causa da narrativa.

"Abrir o fit": a maturidade não zera mais Non-AI; cada produto declara para
quais maturidades serve (catalog), então empresas data-heavy recebem RAPIDS/infra
mesmo sem serem AI-native.
"""
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger
from pydantic import BaseModel, Field

from agents.state import RadarState
from core.llm import get_llm
from recommender.catalog import Confidence, ProductFit, score_products

SYSTEM_PROMPT = """Você é o Recommendation Agent do NVISION. Recebe o perfil de \
uma startup brasileira e uma lista de produtos NVIDIA JÁ SELECIONADOS por regra \
como compatíveis com ela. Sua tarefa é, para CADA produto, escrever UMA frase \
objetiva de COMO aquele produto ajudaria ESTA startup específica a crescer — \
citando o que no perfil dela justifica o uso. Não invente fatos fora do perfil, \
não reordene nem descarte produtos. Devolva um item por produto recebido."""


class TechRecommendation(BaseModel):
    """Uma tecnologia NVIDIA recomendada, com citação e tese de crescimento."""

    tech: str
    url: str
    summary: str                 # o que o produto faz
    confidence: Confidence       # faixa de confiança do match (por regras)
    matched_signals: list[str]   # gatilhos do perfil que casaram (transparência)
    growth: str                  # COMO ajuda a empresa a crescer (LLM ou template)
    snippet: str = ""            # trecho do RAG para citação (se houver)


class StartupRecommendation(BaseModel):
    """Recomendação de stack NVIDIA para UMA startup."""

    name: str
    label: str
    technologies: list[TechRecommendation] = Field(default_factory=list)
    overall_confidence: Confidence = "low"
    notes: list[str] = Field(default_factory=list)


class _GrowthItem(BaseModel):
    tech: str
    growth: str


class _GrowthOutput(BaseModel):
    """Saída estruturada do LLM: a tese de crescimento por produto."""

    items: list[_GrowthItem]


def _perfil_texto(startup: dict) -> str:
    """Texto livre do perfil para o casamento de sinais do catálogo."""
    partes: list[str] = []
    for campo in ("name", "description", "sector"):
        if startup.get(campo):
            partes.append(str(startup[campo]))
    if startup.get("ai_signals"):
        partes.append("; ".join(startup["ai_signals"]))
    if startup.get("tech_stack"):
        partes.append(", ".join(startup["tech_stack"]))
    return ". ".join(partes)


def _snippets_por_tech(chunks: list[dict]) -> dict[str, str]:
    """Do RAG, SÓ para CITAÇÃO: o melhor trecho (maior rerank) por tecnologia.

    A recomendação em si é 100% por regras (catálogo); o RAG não pontua mais —
    entra apenas para anexar um trecho-fonte ao produto recomendado, quando a
    base NVIDIA tiver algo sobre ele."""
    melhor_score: dict[str, float] = {}
    snippet: dict[str, str] = {}
    for c in chunks:
        tech = c["tech"]
        score = c.get("rerank_score", 0.0)
        if tech not in melhor_score or score > melhor_score[tech]:
            melhor_score[tech] = score
            snippet[tech] = c.get("text", "")[:200].strip()
    return snippet


def _escrever_crescimento(startup: dict, fits: list[ProductFit]) -> dict[str, str]:
    """LLM: uma frase de 'como ajuda a crescer' por produto. Resiliente."""
    try:
        llm = get_llm().with_structured_output(_GrowthOutput)
        catalogo = "\n".join(
            f"- {f.tech}: {f.summary} (sinais que casaram: "
            f"{', '.join(f.matched_signals) or 'setor/semântica'})"
            for f in fits
        )
        humano = (
            f"Perfil da startup:\n{_perfil_texto(startup)}\n\n"
            f"Produtos NVIDIA selecionados:\n{catalogo}"
        )
        out: _GrowthOutput = llm.invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=humano)]
        )
        return {i.tech.strip(): i.growth.strip() for i in out.items if i.growth.strip()}
    except Exception:  # narrativa nunca derruba o pipeline — cai no template
        logger.exception("recommendation: LLM de crescimento falhou; usando template")
        return {}


def _recomendar(name: str, label: str, startup: dict,
                chunks: list[dict], usar_llm: bool = True) -> StartupRecommendation:
    """Aplica catálogo (regras) + LLM (narrativa) a UMA startup."""
    snip_por_tech = _snippets_por_tech(chunks)   # RAG só para citação
    produtos = score_products(
        _perfil_texto(startup), startup.get("sector"), label
    )

    if not produtos:
        return StartupRecommendation(
            name=name, label=label,
            notes=["nenhum produto NVIDIA aderente a este perfil"],
        )

    # LLM escreve o 'como ajuda a crescer' (com fallback na tese do catálogo).
    growth_por_tech = _escrever_crescimento(startup, produtos) if usar_llm else {}

    techs = [
        TechRecommendation(
            tech=p.tech,
            url=p.url,
            summary=p.summary,
            confidence=p.confidence,
            matched_signals=p.matched_signals,
            growth=growth_por_tech.get(p.tech, p.growth_thesis),
            snippet=snip_por_tech.get(p.tech, ""),
        )
        for p in produtos
    ]

    notes: list[str] = []
    if label == "Non-AI":
        notes.append(
            "startup Non-AI: priorize os produtos de dado/infra; "
            "os de IA generativa são uma aposta de evolução"
        )

    return StartupRecommendation(
        name=name, label=label, technologies=techs,
        overall_confidence=techs[0].confidence, notes=notes,
    )


def recommendation_node(state: RadarState) -> dict:
    """Nó 8 do grafo: recomenda a stack NVIDIA por startup (catálogo + LLM)."""
    validadas = state.get("validated_startups", [])
    chunks_por_nome = {
        c["name"]: c.get("chunks", []) for c in state.get("rag_contexts", [])
    }

    recomendacoes: list[StartupRecommendation] = []
    com_recomendacao = 0
    for v in validadas:
        startup = v["classified"]["startup"]
        name = startup.get("name", "")
        label = v["classified"]["label"]
        rec = _recomendar(name, label, startup, chunks_por_nome.get(name, []))
        recomendacoes.append(rec)
        if rec.technologies:
            com_recomendacao += 1

    logger.info("recommendation: {} startups recomendadas", com_recomendacao)
    return {
        "recommendations": [r.model_dump() for r in recomendacoes],
        "messages": [
            (
                "ai",
                f"[recommendation] {com_recomendacao}/{len(validadas)} startups "
                f"com stack NVIDIA recomendada (catálogo de regras + LLM)",
            )
        ],
    }
