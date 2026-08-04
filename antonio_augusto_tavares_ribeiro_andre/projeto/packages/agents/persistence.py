"""Persistência das saídas dos agentes nas tabelas relacionais (F4.7 · F6.13).

Ponte entre os nós de saída do grafo e o schema relacional (F0.6). Duas contrapartes do
`persist_profile` (F1.10), uma por artefato:

- **`persist_recommendations` (F4.7):** grava cada `Recommendation` (saída do recommender,
  F4.2/F4.3) na tabela `recommendation` e **liga a evidência dos dois lados** na tabela
  `evidence` polimórfica — o lado startup (`evidencia_gap`) com `field='gap'`, o lado NVIDIA
  (`evidencia_nvidia`, citações da KB) com `field='nvidia'`, ambos sob
  `entity_type='recommendation'` / `entity_id=<rec.id>`.
- **`persist_score` (F6.13):** grava o `AIMIScore` (saída do classifier, F2.6/F6.1) na tabela
  `score` e liga a evidência **de cada pilar** sob `entity_type='score'` / `field=<pilar>`
  (ex.: 'data_moat'). Fecha a lacuna anotada na F6.13 e alimenta os deep-links por pilar da
  UI (`apps/api/schemas.py`), que degradavam sem o AIMI persistido.

Sustentam a auditoria do §8: a decisão prescrita e o diagnóstico ficam rastreáveis até as
fontes que os justificam. O invariante "evidência dos dois lados" da recomendação já é
garantido pelo schema (`Recommendation._require_both_sides`, F0.5) e reforçado pelo Guardrails
(F4.5); aqui ele só é **materializado**.

**Idempotente** (mesmo ethos do upsert de perfil, F1.10): re-rodar a persistência do mesmo run
não duplica — a recomendação casa por `(run_id, company_id, tech)` e o score por
`(run_id, company_id)`; em hit a linha é **enriquecida**, e a evidência dedup por (url, hash,
alvo) via `persist_evidence`. Assim o worker (F2.10) pode reprocessar um run sem inflar linhas.
**Puro/offline** salvo a persistência, que roda via sessão injetada (testável em SQLite). Faz
`flush`, não `commit`: a transação é do caller (worker F2.10 / API F5).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from sqlmodel import select

from packages.db.models import Evidence
from packages.db.models import Recommendation as RecommendationRow
from packages.db.models import Score as ScoreRow
from packages.scraping.provenance import persist_evidence

if TYPE_CHECKING:
    from sqlmodel import Session

    from packages.schemas.aimi import AIMIScore
    from packages.schemas.evidence import Evidence as EvidenceSchema
    from packages.schemas.recommendation import Recommendation

# `entity_type` da evidência na tabela polimórfica (F0.6), por artefato.
_ENTITY = "recommendation"
_SCORE_ENTITY = "score"


def persist_recommendations(
    session: Session,
    recommendations: Sequence[Recommendation],
    *,
    company_id: int,
    run_id: str | None = None,
) -> list[RecommendationRow]:
    """Persiste as recomendações (+ evidência dos dois lados) — F4.7.

    Para cada `Recommendation` (saída do recommender, F4.2/F4.3): faz upsert idempotente da
    linha `recommendation` por `(run_id, company_id, tech)` e registra a evidência de cada
    lado na tabela `evidence` (`field='gap'` lado startup, `field='nvidia'` lado KB). Devolve
    as linhas persistidas, na ordem de entrada. `flush` (não `commit`): a transação é do caller.
    """
    rows: list[RecommendationRow] = []
    for rec in recommendations:
        row = _upsert_recommendation(session, rec, company_id=company_id, run_id=run_id)
        _record_recommendation_evidence(session, row, rec)
        rows.append(row)
    return rows


def _upsert_recommendation(
    session: Session, rec: Recommendation, *, company_id: int, run_id: str | None
) -> RecommendationRow:
    """Upsert idempotente da linha `recommendation` por `(run_id, company_id, tech)`.

    Em hit **enriquece** (a recomendação mais recente do mesmo run/empresa/tech prevalece,
    sem duplicar); em miss insere. `flush` p/ materializar o `id` (alvo da evidência).
    """
    row = session.exec(
        select(RecommendationRow).where(
            RecommendationRow.company_id == company_id,
            RecommendationRow.run_id == run_id,
            RecommendationRow.tech == rec.tech,
        )
    ).first()
    if row is None:
        row = RecommendationRow(company_id=company_id, run_id=run_id, tech=rec.tech)
        session.add(row)

    row.justificativa_tecnica = rec.justificativa_tecnica
    row.justificativa_negocio = rec.justificativa_negocio
    row.prioridade = rec.prioridade
    row.complexidade = rec.complexidade
    row.proxima_acao = rec.proxima_acao
    row.pilar_origem = rec.pilar_origem
    # ROI (F6) é opcional e mora em JSON; serializa só o que houver.
    row.roi = rec.roi.model_dump() if rec.roi else None

    session.flush()
    return row


def _record_recommendation_evidence(
    session: Session, row: RecommendationRow, rec: Recommendation
) -> None:
    """Registra a evidência dos **dois lados** na tabela `evidence` (auditável, §8).

    `field` distingue o lado: `'gap'` (startup — o que no perfil/AIMI motiva) e `'nvidia'`
    (citações da KB recuperadas pelo RAG). Dedup por (url, hash, alvo) via `persist_evidence`.
    """
    for field, evidence_list in (("gap", rec.evidencia_gap), ("nvidia", rec.evidencia_nvidia)):
        for ev in evidence_list:
            persist_evidence(
                session, _evidence_row(ev, entity_type=_ENTITY, entity_id=row.id, field=field)
            )


def persist_score(
    session: Session,
    aimi: AIMIScore,
    *,
    company_id: int,
    run_id: str | None = None,
) -> ScoreRow:
    """Persiste o AIMI (+ evidência por pilar) na tabela `score` — fecha a lacuna da F6.13.

    Contraparte de `persist_recommendations` para a saída do **classifier** (F2.6/F6.1): faz
    upsert idempotente da linha `score` por `(run_id, company_id)` — um diagnóstico por empresa
    por run — e liga a evidência de cada pilar na tabela `evidence` (`entity_type='score'`,
    `field=<pilar>`). Devolve a linha persistida. `flush` (não `commit`): a transação é do caller.
    """
    row = _upsert_score(session, aimi, company_id=company_id, run_id=run_id)
    _record_score_evidence(session, row, aimi)
    return row


def _upsert_score(
    session: Session, aimi: AIMIScore, *, company_id: int, run_id: str | None
) -> ScoreRow:
    """Upsert idempotente da linha `score` por `(run_id, company_id)`.

    Em hit **enriquece** (o diagnóstico mais recente do mesmo run/empresa prevalece, sem
    duplicar); em miss insere. `flush` p/ materializar o `id` (alvo da evidência). O `total` é
    a soma derivada pelo schema (`AIMIScore`), aqui só copiada — fonte única segue o contrato.
    """
    row = session.exec(
        select(ScoreRow).where(
            ScoreRow.company_id == company_id,
            ScoreRow.run_id == run_id,
        )
    ).first()
    if row is None:
        row = ScoreRow(
            company_id=company_id,
            run_id=run_id,
            classificacao=aimi.classificacao,
            total=aimi.total,
            data_moat=aimi.data_moat.score,
            workflow_depth=aimi.workflow_depth.score,
            technical_optimization=aimi.technical_optimization.score,
            distribution_moat=aimi.distribution_moat.score,
        )
        session.add(row)

    row.classificacao = aimi.classificacao
    row.confidence = aimi.confidence
    row.total = aimi.total
    row.inception_priority = aimi.inception_priority
    row.heuristic_version = aimi.heuristic_version
    row.data_moat = aimi.data_moat.score
    row.workflow_depth = aimi.workflow_depth.score
    row.technical_optimization = aimi.technical_optimization.score
    row.distribution_moat = aimi.distribution_moat.score
    row.just_data_moat = aimi.data_moat.justificativa
    row.just_workflow_depth = aimi.workflow_depth.justificativa
    row.just_technical_optimization = aimi.technical_optimization.justificativa
    row.just_distribution_moat = aimi.distribution_moat.justificativa

    session.flush()
    return row


def _record_score_evidence(session: Session, row: ScoreRow, aimi: AIMIScore) -> None:
    """Liga a evidência de **cada pilar** na tabela `evidence` (auditável, §8).

    `field` é o pilar (ex.: 'data_moat') — o mesmo nome de coluna/enum (`AIMIPillar`), que a UI
    lê para o deep-link por pilar. Dedup por (url, hash, alvo) via `persist_evidence`, então
    reprocessar o run não infla linhas.
    """
    for pillar in aimi.pillars:
        for ev in pillar.evidencia:
            persist_evidence(
                session,
                _evidence_row(
                    ev, entity_type=_SCORE_ENTITY, entity_id=row.id, field=pillar.pilar.value
                ),
            )


def _evidence_row(
    ev: EvidenceSchema, *, entity_type: str, entity_id: int, field: str
) -> Evidence:
    """Converte a `Evidence` do schema numa linha da tabela `evidence` polimórfica.

    Preserva a proveniência que a evidência já carrega (base legal LGPD / política de ToS),
    sem re-derivar nada — vale para qualquer alvo (`entity_type`): recomendação (lados
    `gap`/`nvidia`, F4.7) ou score (por pilar, F6.13).
    """
    return Evidence(
        url=str(ev.url),
        snippet=ev.snippet,
        fetched_at=ev.fetched_at,
        content_hash=ev.content_hash,
        source_title=ev.source_title,
        entity_type=entity_type,
        entity_id=entity_id,
        field=field,
        legal_basis=ev.legal_basis.value if ev.legal_basis else None,
        source_policy=ev.source_policy,
    )


__all__ = ["persist_recommendations", "persist_score"]
