"""Descoberta semântica da coorte (F3.10/F5.12 — cohort-RAG) — a camada "premium" do chat.

O chat determinístico (`discovery.parse_query`) traduz a pergunta nos filtros estruturados que a
lista já entende (tech NVIDIA recomendada · classe · piso de AIMI) — forte e reproduzível, mas
**cego a texto livre**: "startups de detecção de fraude", "visão computacional no varejo",
"healthtech" caem em *nenhum filtro* → "toda a coorte". Esta camada fecha esse gap **rankeando por
similaridade semântica** o conjunto que o filtro já recortou, e **cita a evidência** que sustenta
cada match (princípio §8: nada sem fonte rastreável).

Disciplina (igual ao radar de coorte, F6.5): a similaridade é **cosseno em numpy, em memória** sobre
o mesmo embedder do RAG (`packages.rag.embed`) — **não toca o Qdrant**, então **não há** o conflito
de dimensão (256×2048) que só aparece no índice da KB (`index_use_qdrant`). Offline o default é o
`HashingEmbedder` determinístico (sem rede); a flag `embeddings_use_nv` liga o `nv-embedqa` real
(multilíngue, semântica de verdade). Híbrido honesto: o **filtro** (a montante, `list_companies`)
decide *quem entra*; o **resíduo semântico** (`residual_query`) decide *se* re-ordena por relevância
— sem texto livre, mantém a ordem por Inception Priority (comportamento atual preservado).
"""

from __future__ import annotations

import re
import unicodedata
from typing import TYPE_CHECKING, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import select

from packages.agents.discovery import residual_query
from packages.db.models import Evidence, Recommendation, Score
from packages.rag.embed import Embedder, get_embedder
from packages.scoring.cohort_cluster import load_cohort_points

if TYPE_CHECKING:
    from sqlmodel import Session

_TOKEN = re.compile(r"\w+", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    """Tokenização Unicode (NFC + minúsculas) p/ a sobreposição léxica da citação."""
    return _TOKEN.findall(unicodedata.normalize("NFC", text).lower())


class CohortCitation(BaseModel):
    """Fonte citável que sustenta um match da descoberta (espelha `EvidenceOut`, §8)."""

    model_config = ConfigDict(extra="forbid")

    url: str
    snippet: str
    source_title: str | None = None


class CohortHit(BaseModel):
    """Uma empresa no ranking da descoberta: id + similaridade (se semântico) + citação."""

    model_config = ConfigDict(extra="forbid")

    company_id: int
    similaridade: float | None = Field(
        default=None, description="Cosseno 0–1 com a pergunta; None no modo só-filtro."
    )
    citacao: CohortCitation | None = None


class DiscoveryRanking(BaseModel):
    """Resultado da camada semântica: o modo escolhido + os hits já ordenados."""

    model_config = ConfigDict(extra="forbid")

    modo: Literal["filtro", "semantico"]
    hits: list[CohortHit] = Field(default_factory=list)


def load_company_evidence(session: Session) -> dict[int, list[CohortCitation]]:
    """Evidência citável por `company_id`, resolvendo o polimorfismo da tabela `evidence` (§8).

    Junta as fontes ligadas à empresa por três caminhos — direto (`company`), via `score` (cada
    pilar) e via `recommendation` (lados gap/nvidia) — num só pool por empresa, deduplicado por URL
    (a 1ª ocorrência vence). N+1 irrelevante na escala da coorte (dezenas). É o material das
    citações do chat: nenhuma empresa "casa" sem uma fonte real por trás.
    """
    score_owner = {s.id: s.company_id for s in session.exec(select(Score)).all()}
    rec_owner = {r.id: r.company_id for r in session.exec(select(Recommendation)).all()}

    out: dict[int, list[CohortCitation]] = {}
    seen: dict[int, set[str]] = {}
    for ev in session.exec(select(Evidence)).all():
        if ev.entity_type == "company":
            cid: int | None = ev.entity_id
        elif ev.entity_type == "score":
            cid = score_owner.get(ev.entity_id)
        elif ev.entity_type == "recommendation":
            cid = rec_owner.get(ev.entity_id)
        else:
            cid = None
        if cid is None or ev.url in seen.setdefault(cid, set()):
            continue
        seen[cid].add(ev.url)
        out.setdefault(cid, []).append(
            CohortCitation(url=ev.url, snippet=ev.snippet, source_title=ev.source_title)
        )
    return out


def _best_citation(
    query_tokens: set[str], citations: list[CohortCitation]
) -> CohortCitation | None:
    """A fonte mais relevante à pergunta: maior sobreposição léxica com o snippet.

    Léxico (não embedding) de propósito: a citação **explica** o match em palavras que o usuário
    reconhece ("...detecção de **fraude**..."), de forma estável e auditável. Empate / zero
    sobreposição → a 1ª fonte (ainda é a proveniência real da empresa). Sem evidência → `None`.
    """
    if not citations:
        return None
    return max(
        citations,
        key=lambda c: (len(query_tokens & set(_tokenize(c.snippet))), len(c.snippet)),
    )


def _cosine_similarities(texts: list[str], query: str, embedder: Embedder) -> list[float]:
    """Cosseno da pergunta vs cada perfil (numpy, em memória). Normaliza os dois lados (o
    nv-embedqa nem sempre devolve vetores unitários; o hashing já vem L2-normalizado)."""
    if not texts:
        return []
    mat = np.array(embedder.embed_passages(texts), dtype=float)
    q = np.array(embedder.embed_query(query), dtype=float)
    mat_norm = np.linalg.norm(mat, axis=1)
    q_norm = float(np.linalg.norm(q))
    if q_norm == 0.0:
        return [0.0] * len(texts)
    denom = mat_norm * q_norm
    sims = np.where(denom > 0, (mat @ q) / np.where(denom > 0, denom, 1.0), 0.0)
    return [float(s) for s in sims]


def rank_discovery(
    session: Session,
    q: str,
    candidate_ids: list[int],
    *,
    embedder: Embedder | None = None,
) -> DiscoveryRanking:
    """Ordena os candidatos do filtro e anexa a citação de cada um (F3.10).

    `candidate_ids` é o conjunto que o filtro estruturado (`list_companies`, a montante) já
    recortou, **na ordem de Inception Priority**. Se a pergunta tem texto livre
    (`residual_query` não-vazio) → **modo semântico**: re-ordena por cosseno com a pergunta
    (desempate estável pela prioridade original). Senão → **modo filtro**: mantém a ordem. Em ambos,
    cada hit recebe a fonte mais relevante (`_best_citation`). Lista vazia degrada limpo.
    """
    evidence = load_company_evidence(session)
    query_tokens = set(_tokenize(q))

    def _hit(cid: int, sim: float | None) -> CohortHit:
        return CohortHit(
            company_id=cid,
            similaridade=sim,
            citacao=_best_citation(query_tokens, evidence.get(cid, [])),
        )

    if not candidate_ids:
        return DiscoveryRanking(modo="filtro", hits=[])

    if not residual_query(q):
        return DiscoveryRanking(modo="filtro", hits=[_hit(cid, None) for cid in candidate_ids])

    # Modo semântico: rankeia os candidatos com perfil pelo cosseno; mantém a posição de prioridade
    # como desempate (ordem estável) e como fallback p/ quem não tiver ponto/perfil.
    points = {p.id: p for p in load_cohort_points(session)}
    priority_rank = {cid: i for i, cid in enumerate(candidate_ids)}
    ranked = [cid for cid in candidate_ids if cid in points]
    texts = [points[cid].text() for cid in ranked]
    sims = _cosine_similarities(texts, q, embedder or get_embedder())
    sim_by_id = dict(zip(ranked, sims, strict=True))

    ordered = sorted(
        candidate_ids,
        key=lambda cid: (-(sim_by_id.get(cid, -1.0)), priority_rank[cid]),
    )
    return DiscoveryRanking(
        modo="semantico",
        hits=[_hit(cid, sim_by_id.get(cid)) for cid in ordered],
    )


__all__ = [
    "CohortCitation",
    "CohortHit",
    "DiscoveryRanking",
    "load_company_evidence",
    "rank_discovery",
]
