"""Nó **nvidia_rag** (F3.7): retrieve → rerank → evidência NVIDIA **citável**, guiada pelos gaps.

Sexto nó do grafo (ARQUITETURA §3), entre o evidence_validator (F2.7) e o recommender (F4).
Liga F3 ↔ F4: produz o `evidencia_nvidia` (citações da KB) que a `Recommendation` (F0.5) exige
do lado NVIDIA. O nó **não escreve a resposta em linguagem natural** — isso é o recommender
(F4.2, justificativa) e o briefing (F4.4); aqui a "resposta com citações" se materializa como a
**lista de trechos recuperados+reordenados com proveniência** (§8) anexada ao `state.retrieved`.

**Query derivada dos gaps (esclarecimento do doc):** o nó roda **depois** do classifier/AIMI
(F2.6), então a recuperação **não é genérica** — é uma **por gap/tech-candidata**. Os sub-scores
baixos do `AIMIScore` (faixa ausente/emergente, sobretudo **Technical Optimization** = gatilho de
graduação API→NIM) viram a intenção de busca, mapeada para a área de tecnologia NVIDIA que fecha
aquele gap (P3→NIM/TensorRT-LLM/Triton, P1→NeMo/customização, P2→agentes/NeMo Retriever, P4→
Guardrails/AI Enterprise). O **setor** da startup acrescenta a busca de tecnologia de domínio do
§5.5 (saúde→MONAI/Clara, voz→Riva, cyber→Morpheus, robótica→Isaac, simulação→Omniverse). Assim o
`evidencia_nvidia` já chega relevante ao gap que o recommender (F4.2) vai justificar.

**Decisão de design (espinha verde, igual F2.3–F2.7 e todo o F3):** o caminho é
**offline/determinista por default** e reusa o pipeline plugável da F3 sem reabri-lo — a busca
híbrida (`build_retriever`/F3.5, default `HashingEmbedder`+índice in-memory) + o reranker
(`get_reranker`/F3.6, default `LexicalReranker`). Os backends de rede/GPU (nv-embedqa, Qdrant,
NeMo Reranking NIM) entram pelos toggles já existentes (`embeddings_use_nv`/`index_use_qdrant`/
`reranker_use_nv`), sem tocar o nó. Sem `aimi` (espinha offline sem extração/classificação) o nó
é um **no-op limpo** (`{}`, `retrieved` fica `[]`) — grafo verde ponta a ponta (M2/DoD) sem
recuperar evidência sobre um diagnóstico que não existe nem alucinar citação.

**Grounding fora do evidencia_nvidia:** os trechos `source_type="grounding"` (F3.1d — Sequoia/
Emergence/5-layer cake) **definem a rubrica AIMI**, não são tecnologia NVIDIA recomendável; são
filtrados da saída do nó (o recommender cita tech, não a origem conceitual do índice).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache

from packages.rag import (
    HybridRetriever,
    RerankedChunk,
    Reranker,
    build_retriever,
    get_reranker,
)
from packages.schemas import AIMIPillar, AIMIScore, GraphState, RetrievedChunk, StartupProfile
from packages.schemas.aimi import PillarScore

#: Teto da faixa "emergente" (RUBRICA §1): pilar com score ≤ 12 é um **gap** (ausente/emergente)
#: — tem espaço de graduação que justifica recomendação NVIDIA. Acima disso o pilar já está
#: estabelecido/forte e não puxa uma busca dedicada.
GAP_CEILING = 12

#: Quantos gaps viram busca dedicada (os de menor score primeiro) — mantém a recuperação focada
#: e barata (uma por gap, não uma varredura genérica). O setor entra como busca extra à parte.
MAX_GAPS = 3

#: Candidatos puxados da busca híbrida por consulta, antes do rerank (F3.5→F3.6).
RETRIEVE_LIMIT = 8

#: Citações mantidas por consulta depois do rerank (cross-encoder corta o ruído da fusão).
PER_QUERY_TOP_N = 3

#: Teto de citações no `state.retrieved` (bound de contexto p/ o recommender/briefing). O DoD do
#: F3 pede ≥ 2 citações por resposta — com vários gaps isto cabe com folga.
MAX_CITATIONS = 8

#: Gap (pilar do AIMI) → intenção de busca na KB = a tecnologia NVIDIA que **fecha** aquele gap.
#: Os termos são os que aparecem nos docs curados da KB (F3.1), então a busca lexical casa de fato.
PILLAR_QUERIES: dict[AIMIPillar, str] = {
    AIMIPillar.TECHNICAL_OPTIMIZATION: (
        "inferência otimizada self-hosting NIM TensorRT-LLM Triton quantização "
        "fine-tuning GPU graduação de API externa para stack própria"
    ),
    AIMIPillar.DATA_MOAT: (
        "customização de modelos com dados proprietários fine-tuning NeMo "
        "curadoria de dados data flywheel"
    ),
    AIMIPillar.WORKFLOW_DEPTH: (
        "agentes multi-passo orquestração de workflow RAG NeMo Retriever "
        "recuperação com citações"
    ),
    AIMIPillar.DISTRIBUTION_MOAT: (
        "implantação enterprise governança NeMo Guardrails segurança "
        "NVIDIA AI Enterprise"
    ),
}

#: Domínio da startup (setor/descrição) → tecnologia NVIDIA de domínio recomendável (§5.5). Os
#: stems são casados por substring no texto minúsculo do perfil; o primeiro que casar vira a busca
#: de setor (uma startup tem um domínio primário). Espelha o §5.4/§5.5 do case (techs por domínio).
SECTOR_QUERIES: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        ("saúde", "saude", "health", "clínic", "clinic", "médic", "medic", "hospital",
         "diagnóstic", "diagnostic", "imagem médica", "radiolog", "patolog"),
        "MONAI Clara imagem médica saúde diagnóstico federated learning",
    ),
    (
        ("voz", "fala", "áudio", "audio", "call center", "atendimento", "transcri",
         "speech", "voice", "contact center"),
        "Riva ASR TTS reconhecimento e síntese de fala voz",
    ),
    (
        ("segurança", "seguranca", "cyber", "fraude", "fraud", "ameaça", "threat",
         "security", "anomalia", "intrus"),
        "Morpheus cibersegurança detecção de anomalias e fraude",
    ),
    (
        ("robó", "robot", "indústria", "industria", "manufatura", "autonom", "logística"),
        "Isaac robótica simulação e navegação autônoma",
    ),
    (
        ("simulação", "simulacao", "gêmeo digital", "gemeo digital", "digital twin",
         "render", "3d", "metaverso"),
        "Omniverse simulação e gêmeo digital",
    ),
)


@dataclass(frozen=True)
class RagQuery:
    """Uma consulta de recuperação derivada de um gap (ou do setor) — a unidade do F3.7.

    `pilar` é o gap do AIMI que a originou (`None` = busca de setor/domínio); `label` identifica a
    origem no trace/metadado (o recommender lê para ligar a evidência ao `pilar_origem`, F4.1);
    `text` é o que vai à busca híbrida (F3.5) + rerank (F3.6).
    """

    pilar: AIMIPillar | None
    label: str
    text: str


def _gap_sort_key(p: PillarScore) -> tuple[int, int, str]:
    """Chave de ordenação dos gaps — **acoplamento F6.3**: P3 (Technical Optimization), quando é
    gap, vem primeiro; depois por severidade (menor score), desempate estável pelo nome do pilar.

    P3 baixo é **o** gatilho de graduação API→stack — o maior upside NVIDIA (`ALINHAMENTO §8`,
    `RUBRICA §4`). Por isso, quando P3 é gap (score ≤ `GAP_CEILING`), ele **lidera** a seleção e
    **nunca** é cortado pelo teto `MAX_GAPS`: a recomendação de graduação dispara mesmo que outro
    pilar esteja ainda mais baixo. P3 fora da faixa de gap (score > `GAP_CEILING`) **não** recebe
    prioridade — aí valem só severidade/nome, como nos demais pilares (uma startup com P3 forte
    não é alvo de graduação).
    """
    p3_gap = p.pilar is AIMIPillar.TECHNICAL_OPTIMIZATION and p.score <= GAP_CEILING
    return (0 if p3_gap else 1, p.score, p.pilar.value)


def gap_pillars(aimi: AIMIScore) -> list[PillarScore]:
    """Pilares-gap priorizados (P3 primeiro, depois severidade), limitados a `MAX_GAPS`.

    Gap = score ≤ `GAP_CEILING` (ausente/emergente). **Acoplamento F6.3:** Technical Optimization
    baixo **dispara** a recomendação NVIDIA — quando P3 é gap ele encabeça a lista e sobrevive ao
    corte `MAX_GAPS` (vide `_gap_sort_key`); os demais gaps seguem por severidade (menor primeiro).
    Se nenhum pilar é gap (startup madura), usa o **mais baixo** mesmo assim — sempre há uma tech
    NVIDIA que aprofunda o moat, e o nó nunca fica sem consulta a partir de um diagnóstico válido.
    Público: o mapa de regras gap→tech (F4.1) reusa exatamente esta seleção para que o recommender
    recomende sobre os mesmos gaps que o RAG recuperou evidência (consistência gap↔evidência).
    """
    ordered = sorted(aimi.pillars, key=_gap_sort_key)
    gaps = [p for p in ordered if p.score <= GAP_CEILING] or ordered[:1]
    return gaps[:MAX_GAPS]


def _sector_query(profile: StartupProfile | None) -> RagQuery | None:
    """Busca de setor (§5.5) a partir de setor+descrição do perfil; `None` se nada casar."""
    if profile is None:
        return None
    parts: list[str] = []
    if profile.setor is not None:
        parts.append(str(profile.setor.value))
    if profile.descricao is not None:
        parts.append(str(profile.descricao.value))
    text = " ".join(parts).lower()
    if not text:
        return None
    for stems, query in SECTOR_QUERIES:
        if any(stem in text for stem in stems):
            return RagQuery(pilar=None, label="setor", text=query)
    return None


def build_rag_queries(aimi: AIMIScore, profile: StartupProfile | None) -> tuple[RagQuery, ...]:
    """Deriva as consultas do diagnóstico: uma por gap (F2.6) + a de setor (§5.5), na ordem."""
    queries = [
        RagQuery(pilar=p.pilar, label=p.pilar.value, text=PILLAR_QUERIES[p.pilar])
        for p in gap_pillars(aimi)
    ]
    sector = _sector_query(profile)
    if sector is not None:
        queries.append(sector)
    return tuple(queries)


def _citation(reranked: RerankedChunk, query: RagQuery, gaps: Sequence[str]) -> RetrievedChunk:
    """Converte o `RerankedChunk` da KB (F3.6) no `RetrievedChunk` de transporte do grafo (§8).

    O metadado preserva a proveniência citável + a rastreabilidade gap→evidência (F4.1): `pilar`/
    `gap` que ranqueou o trecho, `gaps` (todos os gaps que ele cobre) e os dois scores
    (transparência da fusão F3.5 vs. rerank F3.6).
    """
    return RetrievedChunk(
        text=reranked.text,
        source_url=reranked.url or None,
        source_title=reranked.title or reranked.tech or None,
        score=reranked.rerank_score,
        metadata={
            "chunk_id": reranked.chunk_id,
            "tech": reranked.tech,
            "section": reranked.section,
            "source_type": reranked.source_type,
            "retrieval_score": reranked.retrieval_score,
            "rerank_score": reranked.rerank_score,
            "pilar": query.pilar.value if query.pilar is not None else None,
            "gap": query.label,
            "gaps": list(gaps),
            "query": query.text,
        },
    )


def retrieve_evidence(
    queries: Sequence[RagQuery],
    *,
    retriever: HybridRetriever,
    reranker: Reranker,
) -> tuple[RetrievedChunk, ...]:
    """Roda retrieve→rerank por consulta e funde num conjunto citável deduplicado por trecho.

    Para cada gap/setor: busca híbrida (F3.5) → rerank (F3.6, `top_n` por consulta). Filtra o
    grounding da rubrica (F3.1d — não é tech recomendável). Um trecho que serve a mais de um gap é
    mantido **uma vez**, com o maior `rerank_score` e a lista de gaps que cobre. Ordena por
    relevância (rerank desc, desempate por id) e corta em `MAX_CITATIONS`.
    """
    best: dict[str, tuple[float, RerankedChunk, RagQuery]] = {}
    covers: dict[str, list[str]] = {}
    for query in queries:
        retrieved = retriever.search(query.text, limit=RETRIEVE_LIMIT)
        for rc in reranker.rerank(query.text, retrieved, top_n=PER_QUERY_TOP_N):
            if rc.source_type == "grounding":
                continue  # rubrica AIMI (F3.1d), não tech NVIDIA recomendável
            cid = rc.chunk_id
            seen = covers.setdefault(cid, [])
            if query.label not in seen:
                seen.append(query.label)
            if cid not in best or rc.rerank_score > best[cid][0]:
                best[cid] = (rc.rerank_score, rc, query)
    citations = [
        _citation(rc, query, covers[cid]) for cid, (_, rc, query) in best.items()
    ]
    citations.sort(key=lambda c: (-(c.score or 0.0), c.metadata["chunk_id"]))
    return tuple(citations[:MAX_CITATIONS])


@lru_cache(maxsize=1)
def get_kb_retriever() -> HybridRetriever:
    """Recuperador da KB (F3.5), construído **uma vez** por processo (KB estática, determinística).

    Reusa `build_retriever` (ingest→chunk→embed→index→busca híbrida) com os defaults — offline/
    reproduzível por default; os toggles de rede/GPU da F3 escolhem os backends reais no build. O
    cache evita reindexar a KB a cada run; testes que precisam de isolamento injetam `retriever=`.
    """
    return build_retriever()


def nvidia_rag(
    state: GraphState,
    *,
    retriever: HybridRetriever | None = None,
    reranker: Reranker | None = None,
) -> dict:
    """F3.7 — recupera evidência NVIDIA citável guiada pelos gaps do AIMI; update parcial.

    Sem `aimi` (espinha offline sem classificação) é um no-op limpo (`{}`) — `retrieved` fica `[]`,
    grafo verde (M2/DoD) sem recuperar sobre diagnóstico inexistente. Com diagnóstico, deriva as
    consultas (gaps + setor), roda retrieve→rerank e anexa as citações ao `state.retrieved`, com a
    proveniência e a rastreabilidade gap→evidência que o recommender (F4) consome. `retriever`/
    `reranker` são injetáveis (testes/worker); por default usam a espinha verde plugável da F3.
    """
    aimi = state.aimi
    if aimi is None:
        return {}  # nada a recuperar (offline default) → retrieved [], espinha verde (M2)
    queries = build_rag_queries(aimi, state.profile)
    retriever = retriever or get_kb_retriever()
    reranker = reranker or get_reranker()
    citations = retrieve_evidence(queries, retriever=retriever, reranker=reranker)
    trace = {
        **state.trace,
        "rag": {
            "queries": [{"gap": q.label, "text": q.text} for q in queries],
            "n_citations": len(citations),
            "reranker": reranker.name,
        },
    }
    return {"retrieved": list(citations), "trace": trace}


__all__ = [
    "GAP_CEILING",
    "MAX_GAPS",
    "RETRIEVE_LIMIT",
    "PER_QUERY_TOP_N",
    "MAX_CITATIONS",
    "PILLAR_QUERIES",
    "SECTOR_QUERIES",
    "RagQuery",
    "gap_pillars",
    "build_rag_queries",
    "retrieve_evidence",
    "get_kb_retriever",
    "nvidia_rag",
]
