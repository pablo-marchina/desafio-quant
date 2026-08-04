"""Coorte real → entradas do eval set (F7.1).

Onde o eval set semente (F1.12) é 100% **sintético** (fixtures ancoradas na rubrica, sem
`evidence_urls`), este módulo fecha a metade real da **F7.1**: lê a coorte acumulada pelo
cohort builder (F1.14) na tabela `company` — perfil + `score` (AIMI) + `recommendation` +
`evidence` — e emite entradas `LabeledStartup` com **empresa real**, **`evidence_urls`
rastreáveis** e os rótulos (classe/AIMI/techs) **propostos pelo pipeline**.

**Honestidade (regra do projeto):** o rótulo é a saída do **próprio** modelo, então medir o
modelo contra ele é um **baseline circular** — por isso cada entrada sai com
`label_source='model'` e `load_eval_set()` a mantém **fora do headline** por padrão (só entra
com `include_model=True`). O sourcing/evidência é real e automático; o rótulo é proposto, não
ground-truth (a promoção p/ revisado é trabalho humano à parte).

A região do plano `classe × AIMI` (`PlaneRegion`) **não** existe em produção — é derivada aqui
(`derive_region`) coerente com os validadores direcionais do `LabeledStartup`; quando os
pilares não caem em nenhuma região canônica (ex.: AI-native com P3 emergente 9–12), a entrada
é **pulada** (cai p/ revisão) em vez de poluir o set. Puro salvo a leitura, via sessão injetada
(testável em SQLite) — espelha a disciplina dos demais harnesses do `packages/eval`.
"""

from __future__ import annotations

import argparse
import re
from typing import TYPE_CHECKING

import yaml
from pydantic import ValidationError
from sqlmodel import select

from packages.db.models import Company, Evidence, Score
from packages.db.models import Recommendation as RecommendationRow
from packages.eval.dataset import EVAL_DIR, ExpectedPillars, LabeledStartup
from packages.schemas.enums import Classification, PlaneRegion

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlmodel import Session

# Limiares direcionais espelhando `dataset._check_coherence` (RUBRICA §6): "estabelecido"
# começa em 13; P3 "baixo" (gap NVIDIA, 100% API) = ≤ 8. Se derivarem, a validação do
# `LabeledStartup` é o guard final (entrada incoerente é pulada, não gravada).
_ESTABELECIDO_MIN = 13
_P3_BAIXO_MAX = 8

# Hosts da KB NVIDIA: evidência do **lado NVIDIA** da recomendação, não fonte da startup —
# fora dos `evidence_urls` (que sustentam o rótulo da empresa).
_KB_HOSTS = ("nvidia.com", "build.nvidia.com")


def derive_region(classificacao: Classification, pillars: ExpectedPillars) -> PlaneRegion | None:
    """Região do plano `classe × AIMI` a partir da classe + pilares (RUBRICA §6).

    Coerente com os validadores do `LabeledStartup`. Devolve `None` quando os pilares não
    caem em nenhuma região canônica (AI-native com P3 emergente 9–12, ou non-AI "AI-native
    por IA") — o caller pula a entrada p/ revisão em vez de forçar um rótulo incoerente.
    """
    if classificacao is Classification.NON_AI:
        return PlaneRegion.FORA_ESCOPO if pillars.workflow_depth <= _P3_BAIXO_MAX else None
    if classificacao is Classification.AI_ENABLED:
        return PlaneRegion.PERIFERICO
    # AI-native: a região é função de P3 (otimização) e do max(P1, P2).
    p3 = pillars.technical_optimization
    p1p2 = max(pillars.data_moat, pillars.workflow_depth)
    if p3 >= _ESTABELECIDO_MIN:
        return PlaneRegion.MADURO
    if p3 <= _P3_BAIXO_MAX and p1p2 >= _ESTABELECIDO_MIN:
        return PlaneRegion.ALVO_GRADUACAO
    if p3 <= _P3_BAIXO_MAX:
        return PlaneRegion.WRAPPER
    return None  # P3 emergente (9–12): sem região canônica → revisão


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "empresa"


def _latest_score(session: Session, company_id: int) -> Score | None:
    rows = session.exec(select(Score).where(Score.company_id == company_id)).all()
    return max(rows, key=lambda s: s.id or 0) if rows else None


def _expected_techs(session: Session, company_id: int) -> list[str]:
    rows = session.exec(
        select(RecommendationRow).where(RecommendationRow.company_id == company_id)
    ).all()
    seen: set[str] = set()
    techs: list[str] = []
    for r in rows:  # dedup preservando a ordem de prescrição
        if r.tech not in seen:
            seen.add(r.tech)
            techs.append(r.tech)
    return techs


def _evidence_urls(session: Session, *, company_id: int, score_id: int | None) -> list[str]:
    """URLs que sustentam o rótulo: evidência do perfil (company) + dos pilares (score).

    Exclui a KB NVIDIA (lado da recomendação, não da startup). Dedup preservando a ordem.
    """
    rows = list(
        session.exec(
            select(Evidence).where(
                Evidence.entity_type == "company", Evidence.entity_id == company_id
            )
        ).all()
    )
    if score_id is not None:
        rows += list(
            session.exec(
                select(Evidence).where(
                    Evidence.entity_type == "score", Evidence.entity_id == score_id
                )
            ).all()
        )
    seen: set[str] = set()
    urls: list[str] = []
    for ev in rows:
        url = (ev.url or "").strip()
        if not url or url in seen or any(h in url for h in _KB_HOSTS):
            continue
        seen.add(url)
        urls.append(url)
    return urls


def entry_from_company(
    session: Session, company: Company
) -> tuple[LabeledStartup | None, str | None]:
    """Constrói a entrada de eval (rótulo proposto) de uma empresa da coorte (F7.1).

    Devolve `(entrada, None)` quando coerente, ou `(None, motivo)` quando falta diagnóstico,
    a região não fecha, ou a empresa real fica sem `evidence_urls` (o loader recusa real sem
    fonte) — esses casos caem p/ revisão, não entram no set.
    """
    score = _latest_score(session, company.id)
    if score is None:
        return None, "sem diagnóstico AIMI persistido (score)"

    pillars = ExpectedPillars(
        data_moat=score.data_moat,
        workflow_depth=score.workflow_depth,
        technical_optimization=score.technical_optimization,
        distribution_moat=score.distribution_moat,
    )
    region = derive_region(score.classificacao, pillars)
    if region is None:
        return None, (
            f"pilares sem região canônica "
            f"(classe={score.classificacao.value}, P3={pillars.technical_optimization})"
        )

    evidence_urls = _evidence_urls(session, company_id=company.id, score_id=score.id)
    if not evidence_urls and company.website:
        evidence_urls = [company.website]  # fallback: a home perfilada é fonte rastreável

    justs = [
        j
        for j in (
            score.just_data_moat,
            score.just_workflow_depth,
            score.just_technical_optimization,
            score.just_distribution_moat,
        )
        if j
    ]
    rationale = (
        " ".join(justs)[:600]
        or f"Rótulo proposto pelo pipeline (F7.1) para {company.nome}."
    )

    try:
        entry = LabeledStartup(
            id=f"real-{company.domain or _slug(company.nome)}",
            nome=company.nome,
            setor=company.setor or "desconhecido",
            descricao=company.descricao or company.nome,
            pais=company.pais or "BR",
            classificacao=score.classificacao,
            region=region,
            aimi=pillars,
            # O AIMI que a heurística deu sobre a evidência raspada COMPLETA (F1.14) — o eval usa
            # como predito p/ a real (a `descricao`-resumo afunda no piso). Na geração == `aimi`;
            # a curadoria humana diverge o `aimi` (gold) e preserva este.
            model_aimi=pillars,
            expected_nvidia_techs=_expected_techs(session, company.id),
            rationale=rationale,
            evidence_urls=evidence_urls,
            synthetic=False,
            label_source="model",
            notes=(
                "Auto-rotulado pelo pipeline (F1.14→F7.1); rótulo é baseline circular, "
                "pendente de revisão."
            ),
        )
    except ValidationError as exc:
        return None, f"validação do rótulo falhou: {exc.errors()[0].get('msg', exc)}"
    return entry, None


def cohort_entries(
    session: Session,
) -> tuple[list[LabeledStartup], list[tuple[str, str]]]:
    """Varre as empresas da coorte e devolve `(entradas coerentes, [(empresa, motivo do skip)])`."""
    companies = session.exec(select(Company)).all()
    entries: list[LabeledStartup] = []
    skipped: list[tuple[str, str]] = []
    for company in companies:
        entry, reason = entry_from_company(session, company)
        if entry is not None:
            entries.append(entry)
        else:
            skipped.append((company.domain or company.nome, reason or "incoerente"))
    return entries, skipped


def _entry_to_dict(e: LabeledStartup) -> dict:
    """Serializa uma entrada no formato do YAML do eval (mesma forma de `labeled_startups.yaml`)."""
    return {
        "id": e.id,
        "nome": e.nome,
        "setor": e.setor,
        "descricao": e.descricao,
        "pais": e.pais,
        "classificacao": e.classificacao.value,
        "region": e.region.value,
        "aimi": {
            "data_moat": e.aimi.data_moat,
            "workflow_depth": e.aimi.workflow_depth,
            "technical_optimization": e.aimi.technical_optimization,
            "distribution_moat": e.aimi.distribution_moat,
        },
        **(
            {
                "model_aimi": {
                    "data_moat": e.model_aimi.data_moat,
                    "workflow_depth": e.model_aimi.workflow_depth,
                    "technical_optimization": e.model_aimi.technical_optimization,
                    "distribution_moat": e.model_aimi.distribution_moat,
                }
            }
            if e.model_aimi is not None
            else {}
        ),
        "expected_nvidia_techs": list(e.expected_nvidia_techs),
        "rationale": e.rationale,
        "evidence_urls": list(e.evidence_urls),
        "synthetic": e.synthetic,
        "label_source": e.label_source,
        "notes": e.notes,
    }


def dump_entries(entries: Sequence[LabeledStartup]) -> str:
    """YAML do eval (`entries: [...]`) com cabeçalho explicando a natureza auto-rotulada."""
    header = (
        "# Coorte REAL auto-rotulada pelo pipeline (F1.14 → F7.1).\n"
        "# synthetic: false (empresa real, evidence_urls rastreáveis) | label_source: model.\n"
        "# ATENÇÃO: o rótulo (classe/AIMI/techs) é a saída do PRÓPRIO modelo — medir o modelo\n"
        "# contra ele é um BASELINE CIRCULAR. load_eval_set() mantém estas entradas fora do\n"
        "# headline por padrão (só entram com include_model=True). Gerado por\n"
        "# `python -m packages.eval.cohort_to_eval`; promover exige revisão humana.\n"
    )
    body = yaml.safe_dump(
        {"entries": [_entry_to_dict(e) for e in entries]},
        allow_unicode=True,
        sort_keys=False,
        width=100,
    )
    return header + body


def main(argv: Sequence[str] | None = None) -> int:
    """CLI da F7.1: lê a coorte (F1.14) e materializa as entradas reais auto-rotuladas.

    `--db sqlite:///data/cohort.db` aponta p/ o banco que o cohort builder populou; `--out`
    é o YAML de saída (default `data/eval/cohort_real.yaml`, auto-carregado por `load_eval_set`
    só com `include_model=True`). Imprime o que foi pulado (e por quê) — yield honesto.
    """
    parser = argparse.ArgumentParser(description="Coorte real → eval set (F7.1).")
    parser.add_argument("--db", default=None, help="URL do banco da coorte (default = settings).")
    parser.add_argument(
        "--out", default=str(EVAL_DIR / "cohort_real.yaml"), help="YAML de saída."
    )
    args = parser.parse_args(argv)

    from pathlib import Path

    from sqlmodel import Session, create_engine

    from packages.db.engine import get_engine

    engine = create_engine(args.db) if args.db else get_engine()
    with Session(engine) as session:
        entries, skipped = cohort_entries(session)

    if entries:
        Path(args.out).write_text(dump_entries(entries), encoding="utf-8")
        print(f"escritas {len(entries)} entradas reais (label_source=model) em {args.out}")
    else:
        print("nenhuma entrada real coerente extraída da coorte (ver skips abaixo).")
    print(f"puladas (p/ revisão): {len(skipped)}")
    for sid, reason in skipped:
        print(f"  [skip] {sid}: {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
