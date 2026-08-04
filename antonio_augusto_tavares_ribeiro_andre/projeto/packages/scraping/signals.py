"""Taxonomia de **sinais AI-native** no sourcing (F1.11).

O §2 do brief pede coletar os "sinais de uso intensivo de IA". Este módulo é o
**léxico** desses sinais + um scanner puro que serve a duas pontas do sourcing:

- **enviesa a busca** (`bias_query`): expande a consulta do `search_planner` (F2.3)
  com qualificadores AI-native (PT+EN) para fazer **aflorar** candidatas certas no
  Tavily (F1.1) — recall-first;
- **pré-filtra candidatas** (`prefilter`): pontua o `title`+`snippet` de cada
  `SearchResult` por evidência lexical barata e **descarta as claramente non-AI**
  **antes** da classificação pós-hoc do LLM (F2.6) — poupa quota de LLM (F2.11) e
  foca o grafo nas empresas que importam.

**Não** é o classificador nem o AIMI: é um filtro de *sourcing* (lexical, alto
recall). A **classe** (§5.1) e os **pilares** (`docs/ARQUITETURA.md §3.6`, F2.6) seguem
sendo decididos depois, com evidência. O `CATEGORY_PILLAR` é só uma **dica** de para
onde cada categoria de sinal aponta (Workflow Depth / Technical Optimization), não um
sub-score — daí pesos pequenos e a regra de manter (não cravar).

As categorias casam com as superfícies de coleta de F1: o texto editorial dos
adapters (Firecrawl/trafilatura, F1.2/F1.4) e o texto estrutural do bs4
(`select_text` sobre vagas/stack, F1.5). Tudo **puro/offline** — regex sobre texto,
sem rede — testável como `_parse`/`is_insufficient` dos demais módulos da fase.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from packages.schemas.enums import AIMIPillar

from .search import SearchResult

# Categorias de sinal (ordenadas do mais "marketável" ao mais técnico/verificável).
SignalCategory = Literal["model_ai", "ml_hiring", "research", "public_stack"]

# Léxico por categoria (PT+EN). Termos curtos/ambíguos ("ia", "ai") ficam de fora de
# propósito — são ruído em texto firmográfico; preferimos "inteligência artificial".
# Casamento é por palavra inteira (\b) e case-insensitive (ver `_PATTERNS`).
TAXONOMY: dict[SignalCategory, tuple[str, ...]] = {
    # Uso de IA no produto/copy — sinal mais fraco (pode ser marketing), por isso peso 1.
    "model_ai": (
        "inteligência artificial",
        "artificial intelligence",
        "ia generativa",
        "generative ai",
        "llm",
        "large language model",
        "modelo de linguagem",
        "gpt",
        "transformer",
        "transformers",
        "rag",
        "retrieval augmented",
        "geração aumentada",
        "embedding",
        "embeddings",
        "vector database",
        "banco vetorial",
        "busca vetorial",
        "fine-tuning",
        "fine tuning",
        "fine-tune",
        "ajuste fino",
        "agentes de ia",
        "ai agents",
        "agentic",
        "multiagente",
        "multi-agent",
        "prompt engineering",
        "computer vision",
        "visão computacional",
        "machine learning",
        "aprendizado de máquina",
        "aprendizado de maquina",
        "deep learning",
        "aprendizado profundo",
        "rede neural",
        "neural network",
        "foundation model",
        "modelo fundacional",
        "multimodal",
    ),
    # Vagas de ML/AI eng — time técnico real construindo, não só consumindo API.
    "ml_hiring": (
        "machine learning engineer",
        "ml engineer",
        "mlops",
        "ai engineer",
        "engenheiro de machine learning",
        "engenheiro de ia",
        "data scientist",
        "cientista de dados",
        "research scientist",
        "applied scientist",
        "deep learning engineer",
        "nlp engineer",
    ),
    # Pesquisa/publicação — profundidade técnica verificável.
    "research": (
        "arxiv",
        "neurips",
        "icml",
        "iclr",
        "emnlp",
        "cvpr",
        "preprint",
        "whitepaper",
        "white paper",
        "publicação científica",
        "publicacao cientifica",
        "google scholar",
        "patente",
        "patent",
    ),
    # Stack pública de ML/IA — framework/infra citados em repo, docs ou vagas.
    "public_stack": (
        "pytorch",
        "tensorflow",
        "keras",
        "jax",
        "hugging face",
        "huggingface",
        "langchain",
        "llamaindex",
        "llama index",
        "haystack",
        "qdrant",
        "pinecone",
        "weaviate",
        "milvus",
        "pgvector",
        "faiss",
        "vllm",
        "ollama",
        "triton",
        "tensorrt",
        "cuda",
        "nvidia",
        "nemo",
        "scikit-learn",
        "mlflow",
        "weights & biases",
        "openai api",
        "anthropic",
        "cohere",
        "mistral",
    ),
}

# Peso de cada categoria como sinal de AI-nativeness (model_ai é o mais fraco).
CATEGORY_WEIGHT: dict[SignalCategory, int] = {
    "model_ai": 1,
    "ml_hiring": 2,
    "research": 2,
    "public_stack": 2,
}

# Dica (não-vinculante) de para qual pilar AIMI a categoria tende a apontar. O score
# real dos pilares é F2.6 (rubrica AIMI, ARQUITETURA §3.6), com evidência — aqui é só orientação.
CATEGORY_PILLAR: dict[SignalCategory, AIMIPillar] = {
    "model_ai": AIMIPillar.WORKFLOW_DEPTH,
    "ml_hiring": AIMIPillar.TECHNICAL_OPTIMIZATION,
    "research": AIMIPillar.TECHNICAL_OPTIMIZATION,
    "public_stack": AIMIPillar.TECHNICAL_OPTIMIZATION,
}

# Score mínimo p/ uma candidata sobreviver ao pré-filtro de sourcing: 1 = **qualquer**
# sinal AI. Recall-first — só descarta o que não tem nenhum vestígio de IA; o veredito
# fica com o classificador (F2.6). `STRONG` marca candidatas de sinal forte/múltiplo
# (ex.: priorização na descoberta de coorte).
AI_CANDIDATE_MIN_SCORE = 1
STRONG_CANDIDATE_MIN_SCORE = 3

# Qualificadores p/ enviesar a busca (subconjunto curado da taxonomia: termos com bom
# recall e pouca ambiguidade). Mais que isto dilui a query em vez de focar.
BIAS_TERMS: tuple[str, ...] = (
    "inteligência artificial",
    "IA generativa",
    "LLM",
    "machine learning",
    "RAG",
    "agentes de IA",
)

# Um regex por categoria: alternância dos termos entre \b, IGNORECASE. Rodado sobre o
# texto original (preserva o casing do trecho casado p/ exibição/evidência).
_PATTERNS: dict[SignalCategory, re.Pattern[str]] = {
    cat: re.compile(r"\b(?:" + "|".join(re.escape(t) for t in terms) + r")\b", re.IGNORECASE)
    for cat, terms in TAXONOMY.items()
}


@dataclass(frozen=True)
class Signal:
    """Um sinal AI-native achado no texto. `term` é a forma canônica (lowercased,
    p/ dedup); `matched` é o trecho como apareceu (casing original, p/ citação)."""

    term: str
    category: SignalCategory
    matched: str


@dataclass(frozen=True)
class SignalScan:
    """Resultado do scan de um texto: os sinais distintos e o score agregado."""

    signals: tuple[Signal, ...]

    @property
    def categories(self) -> frozenset[SignalCategory]:
        """Categorias distintas com pelo menos um sinal."""
        return frozenset(s.category for s in self.signals)

    @property
    def score(self) -> int:
        """Soma dos pesos das **categorias** presentes (não conta termo repetido por
        categoria — evita inflar com keyword stuffing)."""
        return sum(CATEGORY_WEIGHT[cat] for cat in self.categories)

    @property
    def is_ai_candidate(self) -> bool:
        """Sobrevive ao pré-filtro de sourcing (qualquer sinal AI; ver threshold)."""
        return self.score >= AI_CANDIDATE_MIN_SCORE

    @property
    def is_strong(self) -> bool:
        """Sinal AI forte/múltiplo (categorias técnicas ou várias categorias)."""
        return self.score >= STRONG_CANDIDATE_MIN_SCORE


def scan(text: str) -> SignalScan:
    """Varre `text` e devolve os sinais AI-native distintos (puro/offline).

    Dedup por (categoria, termo canônico): cada termo conta uma vez por categoria,
    na ordem das categorias da `TAXONOMY` e do texto. Texto vazio → scan sem sinais.
    """
    found: list[Signal] = []
    seen: set[tuple[SignalCategory, str]] = set()
    for category, pattern in _PATTERNS.items():
        for m in pattern.finditer(text):
            matched = m.group(0)
            key = (category, matched.lower())
            if key in seen:
                continue
            seen.add(key)
            found.append(Signal(term=matched.lower(), category=category, matched=matched))
    return SignalScan(signals=tuple(found))


def prefilter(
    results: Iterable[SearchResult],
    *,
    min_score: int = AI_CANDIDATE_MIN_SCORE,
) -> tuple[SearchResult, ...]:
    """Mantém só as candidatas com sinal AI-native, ordenadas por score (desc).

    Pontua `title`+`snippet` de cada `SearchResult` (F1.1) e descarta quem fica abaixo
    de `min_score` — non-AI óbvias saem antes da classificação (F2.6), poupando quota
    de LLM (F2.11). Empates preservam a ordem de relevância original do Tavily (o sort
    é estável). Use `min_score=STRONG_CANDIDATE_MIN_SCORE` p/ priorizar sinal forte.
    """
    scored: list[tuple[int, SearchResult]] = []
    for r in results:
        score = scan(f"{r.title}\n{r.snippet}").score
        if score >= min_score:
            scored.append((score, r))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return tuple(r for _, r in scored)


def bias_query(
    query: str,
    *,
    terms: Sequence[str] = BIAS_TERMS,
    limit: int = 4,
) -> tuple[str, ...]:
    """Gera variantes da consulta enviesadas por sinais AI-native (recall de sourcing).

    Devolve a consulta original **primeiro** (não perde cobertura geral) seguida de até
    `limit` variantes "`query` + qualificador". Dedup preservando ordem. Alimenta a
    descoberta por setor/região (F2.3), onde a query é genérica e precisa do viés AI.
    """
    base = query.strip()
    if not base:
        raise ValueError("query vazia")
    variants = [base, *(f"{base} {t}" for t in terms[: max(0, limit)])]
    return tuple(dict.fromkeys(variants))


__all__ = [
    "SignalCategory",
    "TAXONOMY",
    "CATEGORY_WEIGHT",
    "CATEGORY_PILLAR",
    "AI_CANDIDATE_MIN_SCORE",
    "STRONG_CANDIDATE_MIN_SCORE",
    "BIAS_TERMS",
    "Signal",
    "SignalScan",
    "scan",
    "prefilter",
    "bias_query",
]
