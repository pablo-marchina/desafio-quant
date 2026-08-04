"""Avaliação RAGAS do RAG NVIDIA (F3.9) — faithfulness, answer relevancy, context precision/recall.

Fecha o Entregável 3 (ARQUITETURA §4, marco M3): mede a **qualidade do RAG** (F3.1→F3.7) com as
quatro métricas RAGAS sobre um **conjunto versionado de perguntas NVIDIA** (`data/eval/rag/
questions.yaml`) e gera um **baseline de qualidade versionado** (`data/eval/rag/baseline.json`,
DoD F3). É o que sustenta o princípio "RAGAS no CI" (ARQUITETURA §8): o smoke RAGAS (F0.10)
deixa de ser placeholder e passa a rodar esta avaliação offline a cada push.

Decisões (F3.9), honrando o que já está travado no projeto:

- **Espinha verde offline e determinística** (como F3.1–F3.8 e os nós F2): o default é o
  `LexicalRagasMetrics` — implementação **determinística, sem rede/GPU**, das quatro métricas
  por sobreposição de **tokens de conteúdo** (proxy lexical do juiz). Roda no CI e produz o
  baseline reproduzível, sem LLM/credencial. As definições seguem o RAGAS: faithfulness = frações
  de afirmações da resposta ancoradas nos contextos; answer relevancy = aderência resposta×
  pergunta; context precision = relevância ponderada pela posição (rank-aware); context recall =
  cobertura da referência pelos contextos.
- **Juiz LLM é hook de rede que degrada limpo** — como o `NVEmbedQA` (F3.3), o `QdrantVectorIndex`
  (F3.4) e o `NeMoReranker` (F3.6): o backend `RagasJudge` usa a biblioteca `ragas` + um juiz
  Nemotron (catálogo build.nvidia.com) e levanta `RagasUnavailable` sem a dep/credencial. O
  **run LLM-judged consolidado contra os limiares (faithfulness ≥ 0,80; context recall ≥ 0,70) é
  a F7.3** — aqui o backend fica plugável/reservado, sem antecipar o trabalho da F7 (mesma
  disciplina do Cohere Rerank, reservado na F3.6 até a F7). Troca por config (`ragas_use_llm`,
  off por default) ou injeção.
- **Harness reusável**: a resposta avaliada vem de um `answer_fn` injetável; o default é um
  compositor **extrativo determinístico** (seleciona dos contextos as frases mais próximas da
  pergunta), para as quatro métricas rodarem ponta a ponta hoje sem depender da geração em
  linguagem natural — que é o recommender (F4.2) / briefing (F4.4). A F4/F7 plugam a resposta
  gerada sem reabrir o harness.
- **Tudo tipado (Pydantic) e rastreável** (§8): cada `RagSample` carrega os contextos com
  proveniência citável (`ContextCitation`); o `RagasReport` carimba backend/modelo + o hash do
  dataset de perguntas (proveniência do baseline).
"""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections import Counter
from collections.abc import Callable, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Protocol, runtime_checkable

import yaml
from pydantic import BaseModel, ConfigDict, Field

from packages.config import get_settings
from packages.rag import (
    HybridRetriever,
    RerankedChunk,
    Reranker,
    build_retriever,
    get_reranker,
)

from .dataset import EVAL_DIR

# --- dados versionados --------------------------------------------------------
#: Perguntas NVIDIA e baseline vivem em data/eval/rag/ (subpasta, fora do glob não-recursivo do
#: eval set de classificação em packages/eval/dataset.py — sem colisão de loaders).
RAG_EVAL_DIR = EVAL_DIR / "rag"
QUESTIONS_FILE = RAG_EVAL_DIR / "questions.yaml"
BASELINE_FILE = RAG_EVAL_DIR / "baseline.json"

# --- parâmetros do pipeline de avaliação --------------------------------------
#: Candidatos puxados da busca híbrida por pergunta antes do rerank (igual ao nó F3.7).
RETRIEVE_LIMIT = 8
#: Contextos mantidos por pergunta depois do rerank (a janela que a resposta cita / o juiz lê).
DEFAULT_TOP_CONTEXTS = 4
#: Frases que o compositor extrativo seleciona para a resposta determinística (espinha verde).
ANSWER_SENTENCES = 3

# --- limiares das métricas lexicais (proxy determinístico do juiz) ------------
#: Uma frase está "suportada" se ≥ 50% dos seus tokens de conteúdo aparecem nos contextos
#: (faithfulness) ou na referência→contextos (context recall). Metade já evita casar por acaso.
SUPPORT_THRESHOLD = 0.5
#: Um contexto é "relevante" à referência se cobre ≥ 10% dos tokens de conteúdo dela
#: (context precision) — barra baixa porque cada chunk cobre só um pedaço da resposta ideal.
CTX_RELEVANCE_THRESHOLD = 0.1
#: Casas decimais do arredondamento — torna o baseline estável byte-a-byte entre processos.
ROUND_DP = 6

# --- limiares de qualidade do §7 (F7.3) — o run consolidado checa as duas métricas-alvo do RAG ---
#: Fidelidade da resposta às fontes recuperadas (afirmações ancoradas no contexto). Meta §7.
FAITHFULNESS_GATE = 0.80
#: Cobertura da referência pela recuperação (o RAG trouxe o necessário p/ a resposta). Meta §7.
CONTEXT_RECALL_GATE = 0.70

_TOKEN = re.compile(r"\w+", re.UNICODE)
_SENT = re.compile(r"[.!?\n;:]+")

#: Stopwords PT+EN — removê-las é o que dá sinal às métricas (senão "de/a/o" casariam tudo).
_STOPWORDS = frozenset(
    {
        "a", "o", "os", "as", "um", "uma", "uns", "umas", "de", "do", "da", "dos",
        "das",
        "e", "ou", "que", "com", "sem", "por", "para", "pra", "em", "no", "na", "nos", "nas",
        "ao", "aos", "à", "às", "se", "su", "seu", "sua", "seus", "suas", "como", "mais",
        "menos", "muito", "ja", "já", "the", "of", "and", "or", "to", "in", "on", "for",
        "with", "is", "are", "be", "at", "by", "an", "it", "its", "this", "that",
        "ser", "ter", "tem", "ele", "ela", "isso", "essa", "esse", "qual", "quais", "quando",
        "onde", "não", "nao", "sim", "entre", "sobre", "também", "tambem", "cada", "fazer",
        "faz", "permite", "oferece", "pode", "deve", "está", "esta", "são", "sao",
    }
)


class RagasUnavailable(RuntimeError):
    """Backend de avaliação RAGAS sem infra (lib `ragas`/credencial).

    Sinaliza que o juiz LLM não pode avaliar **agora** — análogo ao `EmbedderUnavailable`
    (F3.3), `IndexUnavailable` (F3.4) e `RerankerUnavailable` (F3.6). Offline a avaliação usa o
    `LexicalRagasMetrics`; não é erro de programação, é o ponto de degradação gracioso. Também
    marca que o run LLM-judged consolidado (com os limiares) é a F7.3, ainda não ligada aqui.
    """


def _tokens(text: str) -> list[str]:
    """Tokenização determinística (NFC, minúsculas, palavras Unicode) — igual a embed/rerank."""
    return _TOKEN.findall(unicodedata.normalize("NFC", text).lower())


def _content_tokens(text: str) -> list[str]:
    """Tokens de conteúdo: sem stopwords e com ≥ 2 caracteres (sinal, não cola gramatical)."""
    return [t for t in _tokens(text) if len(t) > 1 and t not in _STOPWORDS]


def _content_set(text: str) -> set[str]:
    return set(_content_tokens(text))


def _sentences(text: str) -> list[str]:
    """Quebra determinística em frases/itens (pontuação, quebras de linha, bullets via ; :)."""
    return [s.strip() for s in _SENT.split(text) if s.strip()]


def _union(texts: Sequence[str]) -> set[str]:
    """União dos tokens de conteúdo de vários textos (os contextos recuperados)."""
    out: set[str] = set()
    for t in texts:
        out |= _content_set(t)
    return out


def _supported(unit: set[str], support: set[str], threshold: float) -> bool:
    """Uma frase está suportada se uma fração ≥ threshold dos seus tokens está no apoio."""
    if not unit:
        return False
    return len(unit & support) / len(unit) >= threshold


# --- as quatro métricas RAGAS (proxy lexical determinístico) ------------------


def faithfulness(answer: str, contexts: Sequence[str]) -> float:
    """Fração das frases da resposta ancoradas (tokens de conteúdo) na união dos contextos.

    Proxy lexical da faithfulness do RAGAS (afirmações da resposta verificáveis nos contextos).
    Resposta sem frase de conteúdo → 0.0 (não há o que ancorar).
    """
    support = _union(contexts)
    sents = [s for s in (_content_set(s) for s in _sentences(answer)) if s]
    if not sents:
        return 0.0
    supported = sum(_supported(s, support, SUPPORT_THRESHOLD) for s in sents)
    return round(supported / len(sents), ROUND_DP)


def answer_relevancy(answer: str, question: str) -> float:
    """Cosseno das frequências de tokens de conteúdo entre resposta e pergunta (∈[0, 1]).

    Proxy lexical do answer relevancy do RAGAS (a resposta endereça o que foi perguntado) —
    o cosseno normaliza o tamanho, então uma resposta longa cheia de ruído não é premiada.
    """
    qa = Counter(_content_tokens(question))
    aa = Counter(_content_tokens(answer))
    if not qa or not aa:
        return 0.0
    common = set(qa) & set(aa)
    dot = sum(qa[t] * aa[t] for t in common)
    nq = math.sqrt(sum(v * v for v in qa.values()))
    na = math.sqrt(sum(v * v for v in aa.values()))
    if nq == 0.0 or na == 0.0:
        return 0.0
    return round(dot / (nq * na), ROUND_DP)


def context_precision(contexts: Sequence[str], ground_truth: str) -> float:
    """Precisão média (rank-aware): contextos relevantes à referência devem vir no topo.

    Proxy lexical do context precision do RAGAS — average precision sobre a lista ordenada, em
    que um contexto é "relevante" se cobre ≥ `CTX_RELEVANCE_THRESHOLD` dos tokens da referência.
    Sem nenhum contexto relevante → 0.0.
    """
    gt = _content_set(ground_truth)
    if not gt:
        return 0.0
    relevant = [
        len(_content_set(c) & gt) / len(gt) >= CTX_RELEVANCE_THRESHOLD for c in contexts
    ]
    n_relevant = sum(relevant)
    if n_relevant == 0:
        return 0.0
    hits = 0
    ap = 0.0
    for k, is_rel in enumerate(relevant, start=1):
        if is_rel:
            hits += 1
            ap += hits / k
    return round(ap / n_relevant, ROUND_DP)


def context_recall(contexts: Sequence[str], ground_truth: str) -> float:
    """Fração das frases da referência cobertas (tokens de conteúdo) pela união dos contextos.

    Proxy lexical do context recall do RAGAS (a recuperação trouxe o necessário para a resposta
    ideal). Referência sem frase de conteúdo → 0.0.
    """
    support = _union(contexts)
    sents = [s for s in (_content_set(s) for s in _sentences(ground_truth)) if s]
    if not sents:
        return 0.0
    supported = sum(_supported(s, support, SUPPORT_THRESHOLD) for s in sents)
    return round(supported / len(sents), ROUND_DP)


# --- modelos tipados ----------------------------------------------------------


class RagQuestion(BaseModel):
    """Pergunta NVIDIA do conjunto de avaliação (F3.9) — respondível pela KB curada (F3.1)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    question: str
    ground_truth: str = Field(description="Resposta de referência ancorada no texto da KB.")
    reference_techs: tuple[str, ...] = Field(
        default=(), description="Techs que a recuperação deveria trazer (cobertura, F3.8)."
    )


class ContextCitation(BaseModel):
    """Proveniência citável (§8) de um contexto recuperado que entrou na avaliação."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: str
    tech: str
    url: str
    section: str


class RagSample(BaseModel):
    """Amostra montada por pergunta — o que a avaliação RAGAS pontua (pergunta/resposta/ctx)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    question_id: str
    question: str
    answer: str = Field(description="Resposta avaliada (extrativa por default; injetável).")
    contexts: tuple[str, ...] = Field(description="Contextos recuperados+rerankeados (citáveis).")
    ground_truth: str
    citations: tuple[ContextCitation, ...] = Field(description="Proveniência dos contextos (§8).")
    retrieved_techs: tuple[str, ...] = Field(description="Techs dos contextos (cobertura, F3.8).")


class RagasMetrics(BaseModel):
    """As quatro métricas RAGAS de uma amostra (ou as médias agregadas), em [0, 1]."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    faithfulness: float = Field(ge=0.0, le=1.0)
    answer_relevancy: float = Field(ge=0.0, le=1.0)
    context_precision: float = Field(ge=0.0, le=1.0)
    context_recall: float = Field(ge=0.0, le=1.0)

    @property
    def mean(self) -> float:
        """Média simples das quatro métricas — resumo de uma linha da qualidade."""
        return round(
            (
                self.faithfulness
                + self.answer_relevancy
                + self.context_precision
                + self.context_recall
            )
            / 4,
            ROUND_DP,
        )


class RagSampleResult(BaseModel):
    """Resultado por pergunta: métricas + rastreabilidade da cobertura (esperado × recuperado)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    question_id: str
    reference_techs: tuple[str, ...]
    retrieved_techs: tuple[str, ...]
    metrics: RagasMetrics


class RagasReport(BaseModel):
    """Relatório de avaliação RAGAS — o baseline de qualidade versionado (DoD F3)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    backend: str = Field(description="Backend que pontuou (lexical-offline ou ragas-llm).")
    model: str = Field(description="Identificador do backend/juiz (proveniência, §8).")
    dataset_id: str = Field(description="Hash do questions.yaml — proveniência do baseline.")
    n_samples: int
    aggregate: RagasMetrics = Field(description="Médias das quatro métricas sobre o conjunto.")
    per_sample: tuple[RagSampleResult, ...]


class RagasGate(BaseModel):
    """Veredito consolidado do RAGAS (F7.3) contra os limiares-alvo do §7 — faithfulness + recall.

    Derivado do `RagasReport` no momento da checagem (não é serializado no baseline, p/ não mudar o
    schema do `baseline.json`/F3.9). Reporta cada métrica-alvo contra sua meta e o veredito
    duro (ambas ≥ o alvo). As outras duas métricas (answer relevancy / context precision) seguem no
    relatório, mas o §7 declara meta só p/ estas duas — as que sustentam "o RAG não alucina e traz o
    necessário".
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    backend: str = Field(description="Backend que pontuou (lexical-offline ou ragas-llm).")
    faithfulness: float = Field(ge=0.0, le=1.0)
    faithfulness_ok: bool = Field(description=f"faithfulness ≥ {FAITHFULNESS_GATE} (§7).")
    context_recall: float = Field(ge=0.0, le=1.0)
    context_recall_ok: bool = Field(description=f"context recall ≥ {CONTEXT_RECALL_GATE} (§7).")
    meets_gates: bool = Field(description="As duas metas-alvo do §7 batidas.")


# --- backends de avaliação (peça plugável) ------------------------------------


@runtime_checkable
class RagEvaluator(Protocol):
    """Contrato de um backend de avaliação RAGAS (peça plugável).

    `name`/`model` identificam o backend no relatório (§8); `score` pontua uma `RagSample` nas
    quatro métricas. Offline é o `LexicalRagasMetrics`; o juiz LLM é o `RagasJudge` (F3.9/F7.3).
    """

    name: str
    model: str

    def score(self, sample: RagSample) -> RagasMetrics:
        """Pontua a amostra nas quatro métricas RAGAS."""
        ...


class LexicalRagasMetrics:
    """Avaliador offline determinístico (espinha verde) — proxy lexical das quatro métricas RAGAS.

    Sem rede/credencial/GPU e reprodutível entre processos. Roda no CI (smoke RAGAS, F0.10) e
    gera o baseline versionado. O valor real (juiz LLM) vem do `RagasJudge`; este é a espinha que
    mantém a avaliação verde e rastreável.
    """

    name = "lexical-offline"
    model = "tapi-ragas-lexical-v1"

    def score(self, sample: RagSample) -> RagasMetrics:
        return RagasMetrics(
            faithfulness=faithfulness(sample.answer, sample.contexts),
            answer_relevancy=answer_relevancy(sample.answer, sample.question),
            context_precision=context_precision(sample.contexts, sample.ground_truth),
            context_recall=context_recall(sample.contexts, sample.ground_truth),
        )


def _ensure_ragas_importable() -> None:
    """Destrava o import do `ragas` 0.4.3 sob `langchain-community` 0.4.x (conflito de dep, F7.3).

    O `ragas/llms/base.py` importa no topo `from langchain_community.chat_models.vertexai import
    ChatVertexAI` — caminho **removido** no `langchain-community` 0.4.x (o ChatVertexAI migrou p/
    `langchain-google-vertexai`). O `ragas` só usa essa classe num `isinstance`
    (`MULTIPLE_COMPLETION_SUPPORTED`); como o juiz aqui é o **Nemotron** (nunca VertexAI), um
    placeholder satisfaz o import sem puxar a dep do Google nem mexer no `langchain` 1.x do projeto.
    Idempotente e **só age se o caminho real faltar** (não sombreia uma versão futura que o traga).
    """
    import sys

    mod_name = "langchain_community.chat_models.vertexai"
    if mod_name in sys.modules:
        return
    try:  # se um dia o caminho real existir (langchain reintroduzir), prefere ele
        import importlib

        importlib.import_module(mod_name)
    except ModuleNotFoundError:
        import types

        stub = types.ModuleType(mod_name)
        stub.ChatVertexAI = type("ChatVertexAI", (), {})  # placeholder só p/ o isinstance do ragas
        sys.modules[mod_name] = stub


class RagasJudge:
    """Backend **preferido** (dogfood): biblioteca `ragas` + juiz Nemotron via build.nvidia.com.

    Hook de rede: usa o `nvidia_api_key` (catálogo) e o Nemotron como juiz LLM + nv-embedqa como
    embeddings do RAGAS. Levanta `RagasUnavailable` quando a dep `ragas`/a credencial falta, para a
    avaliação cair no `LexicalRagasMetrics` offline. O run **consolidado** contra os limiares
    (faithfulness ≥ 0,80; context recall ≥ 0,70) e a validação on-GPU/credencial são a **F7.3** —
    aqui o backend fica reservado/degradando limpo, sem antecipar o trabalho da F7.
    """

    name = "ragas-llm"

    def __init__(self, *, model: str | None = None, api_key: str | None = None) -> None:
        s = get_settings()
        # Juiz no Nano (fast, greedy, SEM reasoning): o Super-reasoning emitia a CoT em prosa e o
        # parser JSON do RAGAS estourava (statement_generator/fix_output_format → NaN → degradava
        # p/ o léxico). O Nano segue o formato estruturado que cada métrica do RAGAS exige. Override
        # por `model=` se precisar do Super.
        self.model = model or s.nemotron_model_fast
        self.api_key = api_key if api_key is not None else s.nvidia_api_key

    def score(self, sample: RagSample) -> RagasMetrics:
        try:
            _ensure_ragas_importable()  # shim do conflito ragas×langchain-community (F7.3)
            from ragas import EvaluationDataset, evaluate
            from ragas.embeddings import LangchainEmbeddingsWrapper
            from ragas.llms import LangchainLLMWrapper
            from ragas.metrics import (
                Faithfulness,
                LLMContextPrecisionWithReference,
                LLMContextRecall,
                ResponseRelevancy,
            )
        except ImportError as exc:  # dep opcional ausente/quebrada -> degrada p/ offline
            raise RagasUnavailable(
                "ragas não instalado/importável (hook de rede F3.9); offline a avaliação usa o "
                "LexicalRagasMetrics. O run LLM-judged consolidado é a F7.3."
            ) from exc
        if not self.api_key:
            raise RagasUnavailable(
                "NVIDIA_API_KEY ausente p/ o juiz Nemotron (hook F3.9); offline usa o "
                "LexicalRagasMetrics. Consolidação LLM-judged: F7.3."
            )
        try:
            from langchain_nvidia_ai_endpoints import ChatNVIDIA, NVIDIAEmbeddings

            # temperature=0: juiz determinístico + adesão estrita ao JSON que o RAGAS parseia.
            judge = LangchainLLMWrapper(
                ChatNVIDIA(model=self.model, api_key=self.api_key, temperature=0.0)
            )
            embeddings = LangchainEmbeddingsWrapper(
                NVIDIAEmbeddings(model=get_settings().nv_embed_model, api_key=self.api_key)
            )
            dataset = EvaluationDataset.from_list(
                [
                    {
                        "user_input": sample.question,
                        "response": sample.answer,
                        "retrieved_contexts": list(sample.contexts),
                        "reference": sample.ground_truth,
                    }
                ]
            )
            result = evaluate(
                dataset,
                metrics=[
                    Faithfulness(),
                    ResponseRelevancy(),
                    LLMContextPrecisionWithReference(),
                    LLMContextRecall(),
                ],
                llm=judge,
                embeddings=embeddings,
            )
            row = result.to_pandas().iloc[0]
            return RagasMetrics(
                faithfulness=round(float(row["faithfulness"]), ROUND_DP),
                answer_relevancy=round(float(row["answer_relevancy"]), ROUND_DP),
                context_precision=round(
                    float(row["llm_context_precision_with_reference"]), ROUND_DP
                ),
                context_recall=round(float(row["context_recall"]), ROUND_DP),
            )
        except RagasUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 - qualquer falha do juiz degrada p/ offline (F7.3 valida)
            raise RagasUnavailable(
                f"juiz RAGAS indisponível ({type(exc).__name__}: {exc}); offline usa o "
                "LexicalRagasMetrics. Validação on-GPU/credencial é a F7.3."
            ) from exc


def get_evaluator(*, prefer_llm: bool | None = None) -> RagEvaluator:
    """Escolhe o avaliador: juiz LLM (ragas) se ligado, senão o lexical offline determinístico.

    Default vem de `ragas_use_llm` (config, off por default = espinha verde). `prefer_llm`
    sobrepõe (demo/GPU). Offline nunca levanta — o `RagasJudge` só falha ao ser usado (degrade).
    """
    use_llm = get_settings().ragas_use_llm if prefer_llm is None else prefer_llm
    return RagasJudge() if use_llm else LexicalRagasMetrics()


# --- montagem das amostras + execução -----------------------------------------


def compose_extractive_answer(
    question: str, contexts: Sequence[str], *, max_sentences: int = ANSWER_SENTENCES
) -> str:
    """Resposta extrativa determinística: as frases dos contextos mais próximas da pergunta.

    Default do `answer_fn` na espinha verde — pega, dos contextos recuperados, as frases com maior
    sobreposição de tokens de conteúdo com a pergunta (desempate pela ordem de aparição) e as une.
    Por ser literal dos contextos, é fiel por construção (faithfulness alta) e focada na pergunta.
    A resposta **gerada** (recommender/briefing, F4) entra depois por injeção, sem mudar o harness.
    """
    q = _content_set(question)
    scored: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    for ctx in contexts:
        for sent in _sentences(ctx):
            key = sent.lower()
            if key in seen:
                continue
            seen.add(key)
            overlap = len(_content_set(sent) & q)
            if overlap > 0:
                scored.append((overlap, len(scored), sent))
    scored.sort(key=lambda it: (-it[0], it[1]))
    return " ".join(sent for _, _, sent in scored[:max_sentences])


def build_sample(
    question: RagQuestion,
    *,
    retriever: HybridRetriever,
    reranker: Reranker,
    top_contexts: int = DEFAULT_TOP_CONTEXTS,
    answer_fn: Callable[[str, Sequence[str]], str] | None = None,
) -> RagSample:
    """Monta a `RagSample` de uma pergunta: retrieve (F3.5) → rerank (F3.6) → contextos + resposta.

    Filtra o grounding da rubrica (F3.1d — define o AIMI, não é tech recomendável), como o nó F3.7,
    e corta nos `top_contexts` melhores. A resposta vem do `answer_fn` (default extrativo).
    """
    answer_fn = answer_fn or compose_extractive_answer
    retrieved = retriever.search(question.question, limit=RETRIEVE_LIMIT)
    reranked: Sequence[RerankedChunk] = reranker.rerank(question.question, retrieved, top_n=None)
    chosen = [rc for rc in reranked if rc.source_type != "grounding"][:top_contexts]
    contexts = tuple(rc.text for rc in chosen)
    citations = tuple(
        ContextCitation(chunk_id=rc.chunk_id, tech=rc.tech, url=rc.url, section=rc.section)
        for rc in chosen
    )
    return RagSample(
        question_id=question.id,
        question=question.question,
        answer=answer_fn(question.question, contexts),
        contexts=contexts,
        ground_truth=question.ground_truth,
        citations=citations,
        retrieved_techs=tuple(rc.tech for rc in chosen),
    )


@lru_cache
def load_rag_questions() -> tuple[RagQuestion, ...]:
    """Carrega (cacheado) as perguntas NVIDIA de `data/eval/rag/questions.yaml`. IDs são únicos."""
    data = yaml.safe_load(QUESTIONS_FILE.read_text(encoding="utf-8")) or {}
    questions = tuple(RagQuestion.model_validate(q) for q in data.get("questions", []))
    if not questions:
        raise ValueError(f"nenhuma pergunta de RAG carregada de {QUESTIONS_FILE}")
    ids = [q.id for q in questions]
    if len(set(ids)) != len(ids):
        raise ValueError("id de pergunta de RAG duplicado")
    return questions


def _dataset_id() -> str:
    """Hash curto do questions.yaml — carimba qual conjunto gerou o baseline (proveniência, §8)."""
    return hashlib.sha256(QUESTIONS_FILE.read_bytes()).hexdigest()[:16]


def evaluate_rag(
    *,
    evaluator: RagEvaluator | None = None,
    retriever: HybridRetriever | None = None,
    reranker: Reranker | None = None,
    questions: Sequence[RagQuestion] | None = None,
    top_contexts: int = DEFAULT_TOP_CONTEXTS,
    answer_fn: Callable[[str, Sequence[str]], str] | None = None,
) -> RagasReport:
    """Avalia o RAG nas quatro métricas RAGAS sobre o conjunto de perguntas e agrega num relatório.

    Offline/determinístico por default (espinha verde): `build_retriever` (F3.5) + `get_reranker`
    (F3.6) + `LexicalRagasMetrics`. Os backends de rede/GPU entram pelos toggles já existentes
    (`embeddings_use_nv`/`index_use_qdrant`/`reranker_use_nv`/`ragas_use_llm`), sem tocar aqui.
    Tudo injetável (testes/F4/F7).
    """
    evaluator = evaluator or get_evaluator()
    retriever = retriever or build_retriever()
    reranker = reranker or get_reranker()
    questions = questions if questions is not None else load_rag_questions()
    results: list[RagSampleResult] = []
    totals = {
        "faithfulness": 0.0,
        "answer_relevancy": 0.0,
        "context_precision": 0.0,
        "context_recall": 0.0,
    }
    for question in questions:
        sample = build_sample(
            question,
            retriever=retriever,
            reranker=reranker,
            top_contexts=top_contexts,
            answer_fn=answer_fn,
        )
        metrics = evaluator.score(sample)
        for key in totals:
            totals[key] += getattr(metrics, key)
        results.append(
            RagSampleResult(
                question_id=question.id,
                reference_techs=question.reference_techs,
                retrieved_techs=sample.retrieved_techs,
                metrics=metrics,
            )
        )
    n = len(results)
    aggregate = RagasMetrics(**{k: round(v / n, ROUND_DP) for k, v in totals.items()})
    return RagasReport(
        backend=evaluator.name,
        model=evaluator.model,
        dataset_id=_dataset_id(),
        n_samples=n,
        aggregate=aggregate,
        per_sample=tuple(results),
    )


def consolidate(report: RagasReport) -> RagasGate:
    """Consolida o relatório RAGAS (F7.3) contra os limiares-alvo do §7 (faithfulness + recall).

    Veredito duro: as **duas** metas batidas. Vale p/ qualquer backend — offline (proxy lexical, o
    piso) ou o juiz LLM real (`--llm`, o número que vale para o gate de qualidade do §7).
    """
    agg = report.aggregate
    f_ok = agg.faithfulness >= FAITHFULNESS_GATE
    r_ok = agg.context_recall >= CONTEXT_RECALL_GATE
    return RagasGate(
        backend=report.backend,
        faithfulness=agg.faithfulness,
        faithfulness_ok=f_ok,
        context_recall=agg.context_recall,
        context_recall_ok=r_ok,
        meets_gates=f_ok and r_ok,
    )


# --- baseline versionado ------------------------------------------------------


def write_baseline(report: RagasReport | None = None) -> Path:
    """Gera (offline, se `report` for None) e grava o baseline versionado em `baseline.json`."""
    report = report or evaluate_rag()
    RAG_EVAL_DIR.mkdir(parents=True, exist_ok=True)
    BASELINE_FILE.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return BASELINE_FILE


def load_baseline() -> RagasReport:
    """Carrega o baseline de qualidade versionado (F3.9)."""
    return RagasReport.model_validate_json(BASELINE_FILE.read_text(encoding="utf-8"))


def _print_report(report: RagasReport) -> None:
    agg = report.aggregate
    print(f"RAGAS [{report.backend}] dataset={report.dataset_id} n={report.n_samples}")
    print(
        f"  faithfulness={agg.faithfulness}  answer_relevancy={agg.answer_relevancy}  "
        f"context_precision={agg.context_precision}  context_recall={agg.context_recall}  "
        f"mean={agg.mean}"
    )
    for r in report.per_sample:
        m = r.metrics
        print(
            f"  - {r.question_id}: f={m.faithfulness} ar={m.answer_relevancy} "
            f"cp={m.context_precision} cr={m.context_recall}"
        )


def _print_gate(gate: RagasGate) -> None:
    mark = "OK " if gate.meets_gates else "XX "
    fm = "OK" if gate.faithfulness_ok else "XX"
    rm = "OK" if gate.context_recall_ok else "XX"
    print(
        f"{mark}RAGAS consolidado (F7.3 · {gate.backend}) vs §7: "
        f"[{fm}] faithfulness={gate.faithfulness} (≥ {FAITHFULNESS_GATE})  "
        f"[{rm}] context_recall={gate.context_recall} (≥ {CONTEXT_RECALL_GATE})"
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI do RAGAS (F0.10/F3.9 + F7.3): avalia e grava/confere o baseline, ou checa o gate §7.

    Sem flag = espinha offline + grava o baseline (smoke F0.10). `--check` confere drift vs o
    baseline versionado. `--llm` pontua com o **juiz Nemotron real** (lib `ragas`, rede/créditos) —
    o run **consolidado** da F7.3; degrada limpo p/ o proxy lexical se a dep/credencial faltar.
    `--gate` checa os limiares-alvo do §7 (faithfulness ≥ 0,80; context recall ≥ 0,70) e falha
    (exit 1) abaixo. `--llm` e `--gate` **não** sobrescrevem o baseline offline do CI.
    """
    import argparse

    parser = argparse.ArgumentParser(description="Avaliação RAGAS do RAG NVIDIA (F3.9 / F7.3).")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compara com o baseline versionado e falha (exit 1) em caso de drift.",
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="pontua com o juiz Nemotron real (lib ragas) — rede/créditos; run consolidado (F7.3).",
    )
    parser.add_argument(
        "--gate",
        action="store_true",
        help="checa os limiares §7 (faithfulness ≥ 0,80; context recall ≥ 0,70) e falha abaixo.",
    )
    args = parser.parse_args(argv)

    if args.llm:
        try:
            report = evaluate_rag(evaluator=get_evaluator(prefer_llm=True))
        except RagasUnavailable as exc:
            print(f"RAGAS juiz LLM indisponível ({exc}); caindo p/ o proxy lexical offline.")
            report = evaluate_rag()
    else:
        report = evaluate_rag()  # offline por default (espinha verde)
    _print_report(report)

    if args.gate:
        gate = consolidate(report)
        _print_gate(gate)
        return 0 if gate.meets_gates else 1
    if args.check:
        if report != load_baseline():
            print("DRIFT: avaliação RAGAS difere do baseline versionado — rode sem --check.")
            return 1
        print("OK: avaliação RAGAS bate com o baseline versionado.")
        return 0
    if args.llm:
        return 0  # run consolidado ao vivo não sobrescreve o baseline offline do CI
    write_baseline(report)
    print(f"baseline RAGAS escrito em {BASELINE_FILE}")
    return 0


__all__ = [
    "RAG_EVAL_DIR",
    "QUESTIONS_FILE",
    "BASELINE_FILE",
    "RETRIEVE_LIMIT",
    "DEFAULT_TOP_CONTEXTS",
    "ANSWER_SENTENCES",
    "RagasUnavailable",
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
    "RagQuestion",
    "ContextCitation",
    "RagSample",
    "RagasMetrics",
    "RagSampleResult",
    "RagasReport",
    "RagasGate",
    "FAITHFULNESS_GATE",
    "CONTEXT_RECALL_GATE",
    "RagEvaluator",
    "LexicalRagasMetrics",
    "RagasJudge",
    "get_evaluator",
    "compose_extractive_answer",
    "build_sample",
    "load_rag_questions",
    "evaluate_rag",
    "consolidate",
    "write_baseline",
    "load_baseline",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
