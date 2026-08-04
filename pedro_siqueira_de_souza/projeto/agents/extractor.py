"""Extractor Agent — quarta estação do grafo.

O Enricher coleta o TEXTO BRUTO de cada startup; o Extractor o transforma em
DADOS ESTRUTURADOS via LLM com saída estruturada (`with_structured_output`),
o mesmo padrão do Search Planner. Para cada startup com `content`, pede ao LLM
para extrair produto, setor, estágio, funding, stack e — o mais importante —
os SINAIS DE IA (evidências textuais) que o Classifier vai usar depois.

Decisões de design:
  - Uma chamada de LLM POR STARTUP (não em lote): erro isolado por item (mesma
    disciplina do scraper/enricher) e contexto focado, sem contaminação entre
    startups. Batching fica como otimização futura.
  - `content=None` => extração SEM LLM: monta o mínimo a partir de name/sector.
    Sem evidência textual, perguntar ao LLM só convidaria alucinação — o jeito
    mais honesto de "não inventar" é não perguntar.
  - `extraction_basis` ("content"/"metadata") sinaliza de onde veio cada
    extração — um sinal de confiança barato pro evidence_validator adiante.
  - Erro POR STARTUP: uma extração que falha vira fallback metadata + log, não
    derruba as demais.

Por que DOIS schemas: o LLM preenche só os campos que dependem do texto
(`_ExtractedFields`). `name` e `extraction_basis` são controlados pelo NÓ — a
identidade vem do RawStartup (não se inventa o nome) e a base de extração é um
fato que o nó conhece, não o LLM. O nó costura os dois em `StructuredStartup`.
"""
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger
from pydantic import BaseModel, Field

from agents.state import RadarState
from core.llm import get_llm

SYSTEM_PROMPT = """Você é o Extractor do NVISION. A partir do texto público \
coletado de uma startup brasileira, extraia dados estruturados.

Regras:
- Extraia SOMENTE o que estiver no texto. Não infira, não complete, não \
invente. Deixe nulo (ou lista vazia) todo campo sem evidência clara.
- `description`: uma a duas frases sobre o produto/serviço da startup.
- `sector`: setor de atuação, normalizado (ex.: "fintech", "healthtech", \
"agtech").
- `stage`: estágio/maturidade apenas se citado (ex.: "seed", "série A").
- `funding`: rodadas ou valores de investimento, apenas se citados.
- `tech_stack`: tecnologias/ferramentas mencionadas no texto.
- `ai_signals`: o MAIS IMPORTANTE — liste evidências TEXTUAIS de que a startup \
usa ou desenvolve inteligência artificial (trechos como "modelos próprios de \
ML", "assistente com LLM", "visão computacional"). Cada item deve estar \
ancorado no texto. Se não houver menção a IA, devolva lista vazia.
"""


class _ExtractedFields(BaseModel):
    """Campos que o LLM extrai do texto. `name` e `extraction_basis` ficam de
    fora de propósito: são controlados pelo nó (ver docstring do módulo).

    Defaults nulos/vazios reforçam a regra de não inventar — o LLM deixa em
    branco o que não tiver evidência.
    """

    description: str | None = None
    sector: str | None = None
    stage: str | None = None
    funding: str | None = None
    tech_stack: list[str] = Field(default_factory=list)
    ai_signals: list[str] = Field(default_factory=list)


class StructuredStartup(BaseModel):
    """Startup já estruturada — saída do Extractor, consumida pelo Classifier."""

    name: str
    description: str | None = None
    sector: str | None = None
    stage: str | None = None
    funding: str | None = None
    tech_stack: list[str] = Field(default_factory=list)
    ai_signals: list[str] = Field(default_factory=list)
    # De onde veio a extração: "content" (texto da página) ou "metadata"
    # (só name/sector, sem conteúdo). Sinal de confiança para etapas seguintes.
    extraction_basis: Literal["content", "metadata"] = "content"


def _so_metadata(name: str, sector: str | None) -> StructuredStartup:
    """StructuredStartup mínimo, SEM LLM: usado quando não há conteúdo (ou
    quando a extração falhou). Só o que sabemos de fato — sem inventar nada."""
    return StructuredStartup(name=name, sector=sector, extraction_basis="metadata")


def _extrair_campos(structured_llm, name: str, content: str) -> _ExtractedFields:
    """Uma chamada de LLM para uma startup. `structured_llm` já vem com
    `with_structured_output(_ExtractedFields)` aplicado."""
    prompt = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Startup: {name}\n\nConteúdo coletado:\n{content}"),
    ]
    return structured_llm.invoke(prompt)


def extractor_node(state: RadarState) -> dict:
    """Nó 4 do grafo: estrutura as startups cruas em StructuredStartup."""
    raw_startups = state.get("raw_startups", [])

    estruturadas: list[StructuredStartup] = []
    via_conteudo = 0
    via_metadata = 0
    # Instanciado preguiçosamente: só pagamos o custo do LLM se houver de fato
    # conteúdo a extrair (startups só-metadata nem tocam nessa costura).
    structured_llm = None

    for rs in raw_startups:
        name = rs.get("name", "")
        sector_hint = rs.get("sector")
        content = rs.get("content")

        if not content:
            estruturadas.append(_so_metadata(name, sector_hint))
            via_metadata += 1
            continue

        try:
            if structured_llm is None:
                structured_llm = get_llm().with_structured_output(_ExtractedFields)
            fields = _extrair_campos(structured_llm, name, content)
            estruturadas.append(
                StructuredStartup(
                    name=name,
                    description=fields.description,
                    # Prefere o setor que o LLM confirmou; se vazio, mantém a
                    # dica que a fonte já trazia (ex.: ranking da 100 Open).
                    sector=fields.sector or sector_hint,
                    stage=fields.stage,
                    funding=fields.funding,
                    tech_stack=fields.tech_stack,
                    ai_signals=fields.ai_signals,
                    extraction_basis="content",
                )
            )
            via_conteudo += 1
        except Exception:  # uma startup não pode derrubar as outras
            logger.exception("extractor falhou em {}", name)
            estruturadas.append(_so_metadata(name, sector_hint))
            via_metadata += 1

    return {
        "extracted_startups": [s.model_dump() for s in estruturadas],
        "messages": [
            (
                "ai",
                f"[extractor] {len(estruturadas)} estruturadas "
                f"({via_conteudo} via conteúdo, {via_metadata} via metadata)",
            )
        ],
    }
