"""Consulta da lista de empresas para o `GET /companies` (F5.2; facetas F5.4/F5.11).

Projeta a tabela `company` (§2) cruzada com o `Score` (AIMI/classe/inception_priority) do
run **mais recente** e com as techs recomendadas (`recommendation`, F4.3), aplicando os
filtros da lista: setor/AIMI/classe (F5.4) + as duas facetas de tecnologia (F5.11) — a tech
que a startup **usa** (`Company.tecnologias`, sinais F1.11/F2.5) e a tech NVIDIA
**recomendada**. A ordenação default é por `inception_priority` desc (a fila de outreach do
gerente, F6.13), com o AIMI como desempate.

Determinístico e portável (SQLite no teste, Postgres em prod): carrega as linhas e resolve
"score mais recente por empresa" + facetas de tech em Python — o volume é de ferramenta
interna. As tags de tech passam pelo **vocabulário controlado** (`packages.schemas.tech_vocab`,
F5.11): grafias soltas colapsam numa tag canônica e o filtro casa por **igualdade** sobre ela
(`list_tech_facets` expõe as tags disponíveis p/ a UI só oferecer o que existe). `flush`/leitura
só; a sessão é do caller (dependência da API).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlmodel import select

from packages.db.models import Company, Evidence, Score
from packages.db.models import Recommendation as RecommendationRow
from packages.schemas.aimi import band_for
from packages.schemas.enums import AIMIPillar, Priority
from packages.schemas.tech_vocab import normalize_techs, tech_matches

from .schemas import (
    CompanyDetailOut,
    CompanyOut,
    EvidenceOut,
    PillarOut,
    RecommendationOut,
    ROIOut,
)

if TYPE_CHECKING:
    from sqlmodel import Session

# Pilares do AIMI na ordem canônica (RUBRICA §1) → coluna do sub-score + coluna da
# justificativa no `Score` (F0.6). É a ordem em que o radar (F5.5) desenha os eixos.
_PILLAR_COLUMNS: tuple[tuple[AIMIPillar, str, str], ...] = (
    (AIMIPillar.DATA_MOAT, "data_moat", "just_data_moat"),
    (AIMIPillar.WORKFLOW_DEPTH, "workflow_depth", "just_workflow_depth"),
    (AIMIPillar.TECHNICAL_OPTIMIZATION, "technical_optimization", "just_technical_optimization"),
    (AIMIPillar.DISTRIBUTION_MOAT, "distribution_moat", "just_distribution_moat"),
)

# Ordem dos cartões de recomendação (F5.6): alta → média → baixa, igual ao briefing (F4.4).
_PRIORITY_RANK: dict[Priority, int] = {Priority.ALTA: 0, Priority.MEDIA: 1, Priority.BAIXA: 2}


def _latest_scores(session: Session) -> dict[int, Score]:
    """Score AIMI mais recente por `company_id` (o diagnóstico vigente da empresa)."""
    latest: dict[int, Score] = {}
    for sc in session.exec(select(Score)).all():
        cur = latest.get(sc.company_id)
        if cur is None or sc.created_at > cur.created_at:
            latest[sc.company_id] = sc
    return latest


def _recommended_techs(session: Session) -> dict[int, list[str]]:
    """Tags NVIDIA recomendadas por `company_id` (faceta (b) do filtro F5.11), normalizadas.

    Colapsa o rótulo de exibição da `Recommendation` ("NVIDIA NIM", "NeMo Retriever (RAG)") na
    tag canônica do vocabulário controlado e deduplica por empresa.
    """
    raw: dict[int, list[str]] = {}
    for row in session.exec(select(RecommendationRow)).all():
        raw.setdefault(row.company_id, []).append(row.tech)
    return {cid: normalize_techs(techs) for cid, techs in raw.items()}


def _sort_key(company: CompanyOut) -> tuple:
    """Ordena por inception_priority desc, AIMI desc (None por último) e nome asc."""
    ip, aimi = company.inception_priority, company.aimi_total
    return (ip is None, -(ip or 0), aimi is None, -(aimi or 0), company.nome.lower())


def list_companies(
    session: Session,
    *,
    setor: str | None = None,
    classificacao: str | None = None,
    min_aimi: int | None = None,
    tech: str | None = None,
    nvidia_tech: str | None = None,
    limit: int = 50,
) -> list[CompanyOut]:
    """Lista as empresas projetadas + filtradas para a UI (F5.4/F5.11).

    Filtros (todos opcionais, combinam em AND): `setor` (igualdade case-insensitive),
    `classificacao` (classe AIMI, ex.: "AI-native"), `min_aimi` (total ≥ corte, exige score),
    `tech` (a startup usa) e `nvidia_tech` (recomendada). Ordena por `inception_priority` e
    corta em `limit`. Empresa sem score só aparece quando nenhum filtro de diagnóstico a exige.
    """
    scores = _latest_scores(session)
    rec_techs = _recommended_techs(session)

    out: list[CompanyOut] = []
    for company in session.exec(select(Company)).all():
        sc = scores.get(company.id)
        usadas = normalize_techs(company.tecnologias)
        nvidia = rec_techs.get(company.id, [])

        if setor and (company.setor or "").lower() != setor.lower():
            continue
        if classificacao and (
            sc is None or sc.classificacao.value.lower() != classificacao.lower()
        ):
            continue
        if min_aimi is not None and (sc is None or sc.total < min_aimi):
            continue
        if not tech_matches(tech, usadas) or not tech_matches(nvidia_tech, nvidia):
            continue

        out.append(
            CompanyOut(
                id=company.id,
                nome=company.nome,
                setor=company.setor,
                pais=company.pais,
                website=company.website,
                classificacao=sc.classificacao.value if sc is not None else None,
                aimi_total=sc.total if sc is not None else None,
                inception_priority=sc.inception_priority if sc is not None else None,
                tecnologias=usadas,
                nvidia_techs=nvidia,
            )
        )

    out.sort(key=_sort_key)
    return out[:limit]


def list_tech_facets(session: Session) -> tuple[list[str], list[str]]:
    """Tags de tech disponíveis para os filtros da lista (F5.11): (usadas, recomendadas).

    Varre **toda** a coorte (independe dos filtros vigentes) e devolve o vocabulário controlado
    de cada faceta — as tags que a startup **usa** (`Company.tecnologias`) e as tags NVIDIA
    **recomendadas** (`Recommendation`), normalizadas, deduplicadas e ordenadas (case-insensitive).
    A UI monta os controles a partir disto: o filtro só oferece tags que existem (determinístico).
    """
    used: set[str] = set()
    for company in session.exec(select(Company)).all():
        used.update(normalize_techs(company.tecnologias))
    nvidia: set[str] = set()
    for techs in _recommended_techs(session).values():
        nvidia.update(techs)

    def _key(tag: str) -> str:
        return tag.lower()

    return sorted(used, key=_key), sorted(nvidia, key=_key)


def _latest_score_for(session: Session, company_id: int) -> Score | None:
    """O `Score` AIMI mais recente de **uma** empresa (o diagnóstico vigente p/ o detalhe)."""
    latest: Score | None = None
    for sc in session.exec(select(Score).where(Score.company_id == company_id)).all():
        if latest is None or sc.created_at > latest.created_at:
            latest = sc
    return latest


def _evidence_by_field(
    session: Session, entity_type: str, entity_id: int
) -> dict[str, list[EvidenceOut]]:
    """Evidência de uma entidade agrupada por `field` (proveniência polimórfica, §8).

    Lê as linhas `evidence` com `entity_type`/`entity_id` e indexa por `field` — o pilar que a
    fonte sustenta no score (F5.5: `field=<pilar>`) ou o lado da recomendação (F5.6: `field='gap'`
    da startup / `field='nvidia'` da KB). Pode vir vazia (degrada gracioso: o item mostra-se sem
    o link).
    """
    grouped: dict[str, list[EvidenceOut]] = {}
    rows = session.exec(
        select(Evidence).where(
            Evidence.entity_type == entity_type, Evidence.entity_id == entity_id
        )
    ).all()
    for ev in rows:
        grouped.setdefault(ev.field or "", []).append(
            EvidenceOut(url=ev.url, snippet=ev.snippet, source_title=ev.source_title)
        )
    return grouped


def _recommendation_cards(session: Session, company_id: int) -> list[RecommendationOut]:
    """Cartões de recomendação de uma startup (§5.5/F5.6), ordenados por prioridade.

    Projeta as linhas `recommendation` (F4.3/F4.7) da empresa com a **evidência dos dois lados**
    (`field='gap'`/`field='nvidia'`, via `_evidence_by_field`) e o `roi` opcional (F6, JSON →
    `ROIOut`; ausente quando a matriz/benchmark ainda não existe). Ordena alta→média→baixa, igual
    ao briefing (F4.4) — a UI só renderiza na ordem que recebe.
    """
    rows = sorted(
        session.exec(
            select(RecommendationRow).where(RecommendationRow.company_id == company_id)
        ).all(),
        key=lambda r: _PRIORITY_RANK.get(r.prioridade, 1),
    )
    cards: list[RecommendationOut] = []
    for row in rows:
        evidence = _evidence_by_field(session, "recommendation", row.id)
        cards.append(
            RecommendationOut(
                tech=row.tech,
                prioridade=row.prioridade.value,
                complexidade=row.complexidade.value,
                justificativa_tecnica=row.justificativa_tecnica,
                justificativa_negocio=row.justificativa_negocio,
                proxima_acao=row.proxima_acao,
                pilar_origem=row.pilar_origem.value if row.pilar_origem else None,
                roi=ROIOut.model_validate(row.roi) if row.roi else None,
                evidencia_gap=evidence.get("gap", []),
                evidencia_nvidia=evidence.get("nvidia", []),
            )
        )
    return cards


def get_company_detail(session: Session, company_id: int) -> CompanyDetailOut | None:
    """Detalhe de uma startup (F5.5/F5.6): perfil + radar AIMI + cartões de recomendação.

    Achata a `Company` (§2) com o `Score` mais recente — os 4 sub-scores, suas faixas
    (`band_for`), justificativas e as fontes citáveis por pilar (F5.5) — e os **cartões de
    recomendação** (F5.6: justificativas, evidência dos dois lados e ROI opcional), com o resumo
    `nvidia_techs` derivado deles. `None` quando a empresa não existe (404 na rota). Empresa sem
    score sai com `pilares=[]` (degrada como a lista). `flush`/leitura só.
    """
    company = session.get(Company, company_id)
    if company is None:
        return None

    sc = _latest_score_for(session, company_id)
    recomendacoes = _recommendation_cards(session, company_id)
    # Resumo de tags (vocabulário controlado, F5.11) — os cartões abaixo guardam o rótulo completo.
    nvidia = normalize_techs([rec.tech for rec in recomendacoes])

    pilares: list[PillarOut] = []
    if sc is not None:
        evidence = _evidence_by_field(session, "score", sc.id)
        for pilar, score_col, just_col in _PILLAR_COLUMNS:
            value = getattr(sc, score_col)
            pilares.append(
                PillarOut(
                    pilar=pilar.value,
                    score=value,
                    band=band_for(value).value,
                    justificativa=getattr(sc, just_col),
                    evidencias=evidence.get(pilar.value, []),
                )
            )

    return CompanyDetailOut(
        id=company.id,
        nome=company.nome,
        setor=company.setor,
        pais=company.pais,
        website=company.website,
        descricao=company.descricao,
        ano_fundacao=company.ano_fundacao,
        classificacao=sc.classificacao.value if sc is not None else None,
        aimi_total=sc.total if sc is not None else None,
        inception_priority=sc.inception_priority if sc is not None else None,
        confidence=sc.confidence if sc is not None else None,
        heuristic_version=sc.heuristic_version if sc is not None else None,
        pilares=pilares,
        nvidia_techs=nvidia,
        recomendacoes=recomendacoes,
    )


__all__ = ["list_companies", "list_tech_facets", "get_company_detail"]
