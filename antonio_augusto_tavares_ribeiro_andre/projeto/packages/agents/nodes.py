"""Nós do grafo multi-agente (F2) — esqueleto.

Cada função é um **nó** do grafo LangGraph (ARQUITETURA §3): recebe o `GraphState`
e devolve um *update parcial* (dict só com os campos que muda). A montagem e as
arestas ficam em `graph.py` (F2.1).

Na F2.1 os corpos são **placeholders deterministas** (sem rede/LLM): provam que o
grafo roda ponta a ponta e produz um briefing rascunho (M2 / DoD "grafo end-to-end
sem RAG ainda"). Cada nó é preenchido pela sua task, anotada no docstring:

- search_planner    → F2.3 (query → termos + fontes priorizadas; ver `search_planner.py`)
- scraper           → F2.4 (map paralelo sobre fontes; usa F1)
- extractor         → F2.5 (Nemotron-Super: docs → StartupProfile + persist)
- classifier        → F2.6 (classe §5.1 + AIMI v0)
- evidence_validator → F2.7 (regra de N fontes; retry via Command; ver `evidence_validator.py`)
- nvidia_rag        → F3   (RAG híbrido Qdrant + NeMo rerank → citações)
- recommender       → F4.2/F4.3 (gaps do AIMI × evidência NVIDIA; ver `recommender.py`)
- gpu_benchmark     → F6   (ROI real na GPU; condicional ★)
- human_review      → F2.8 (HITL interrupt antes do briefing; ver `human_review.py`)
- briefing          → F4.4 (briefing executivo; Guardrails F4.5)

Os updates parciais usam a semântica default do LangGraph (sobrescrita por canal).
Reducers de acumulação (ex.: `raw_docs` no map do scraper) entram com o nó dono.
"""

from __future__ import annotations

from packages.benchmark.matrix import load_matrix, roi_for
from packages.config import get_settings
from packages.schemas import GraphState

from .briefing import briefing  # F4.4 — implementação real do nó (normal + terminais)
from .classifier import classifier  # F2.6 — implementação real do nó
from .evidence_validator import evidence_validator  # F2.7 — implementação real do nó
from .extractor import extractor  # F2.5 — implementação real do nó
from .human_review import human_review  # F2.8 — implementação real do nó
from .nvidia_rag import nvidia_rag  # F3.7 — implementação real do nó
from .recommender import recommender  # F4.2/F4.3 — implementação real do nó
from .scraper import scraper  # F2.4 — implementação real do nó
from .search_planner import search_planner  # F2.3 — implementação real do nó


def gpu_benchmark(state: GraphState) -> dict:
    """F6 — GPU Graduation Engine: anexa o ROI da matriz às recs de graduação (F6.9–F6.11).

    **No-op (espinha verde) por padrão** — devolve `{}` sem recs, com a flag
    `gpu_benchmark_use_matrix` off, ou sem matriz no disco (recs degradam graciosas, sem ROI). Com a
    flag ligada e a matriz presente (`data/benchmark/matrix.json`), deriva o `ROIEstimate` (F0.5) do
    tier configurado e o anexa às recs da família de inferência (NIM/TensorRT-LLM/Triton) que ainda
    não têm ROI — o downstream (persist → API → UI `RoiStrip` / briefing) já consome. `model_copy`
    preserva a evidência dos dois lados intacta (não re-valida); só preenche `roi`.
    """
    recs = state.recommendations
    if not recs or not get_settings().gpu_benchmark_use_matrix:
        return {}
    matrix = load_matrix()
    if matrix is None:
        return {}
    tier = get_settings().benchmark_tier
    updated = list(recs)
    attached = 0
    for i, rec in enumerate(recs):
        if rec.roi is not None:
            continue
        roi = roi_for(rec.tech, tier=tier, matrix=matrix)
        if roi is not None:
            updated[i] = rec.model_copy(update={"roi": roi})
            attached += 1
    if attached == 0:
        return {}
    trace = {**state.trace, "gpu_benchmark": {"roi_attached": attached, "tier": tier}}
    return {"recommendations": updated, "trace": trace}


# Registro nome → função, consumido pela montagem do grafo (graph.py). O `human_review`
# (F2.8) é um nó de **controle HITL** (não um dos 9 agentes), inserido antes do briefing.
NODES = {
    "search_planner": search_planner,
    "scraper": scraper,
    "extractor": extractor,
    "classifier": classifier,
    "evidence_validator": evidence_validator,
    "nvidia_rag": nvidia_rag,
    "recommender": recommender,
    "gpu_benchmark": gpu_benchmark,
    "human_review": human_review,
    "briefing": briefing,
}
