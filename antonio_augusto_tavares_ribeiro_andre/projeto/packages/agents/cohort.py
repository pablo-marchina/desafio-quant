"""Cohort builder — sourcing em lote (F1.14).

Onde o `run_pipeline` (F2) perfila **uma** empresa, este módulo transforma o crawl dos
portfólios/diretórios §9 (F1.6) numa **fila de empresas candidatas** e roda o grafo em
**lote**, acumulando na tabela `company`. É essa tabela acumulada que alimenta o
clustering de coorte (F6.5–F6.7) e a **expansão real do eval set (F7.1)** — não a saída de
um run único. Esclarece o salto "run por-empresa → visão de coorte".

Reusa o que já existe — **não** reimplementa coleta, grafo nem persistência:

- **descoberta:** `scraping.seeds.allowlist` (§9, gate de ToS F1.15) + `scraping.crawler.crawl`
  (F1.6) varrem os portfólios/notícias `allow`; os **links de saída** das páginas são a
  matéria-prima das candidatas (cada domínio externo = uma startup a perfilar).
- **perfilagem:** `agents.graph.run_pipeline` (F2) por empresa, no caminho real atrás de
  `settings.scraper_use_network` (sem a flag o scraper é no-op e o perfil sai vazio).
- **persistência:** `scraping.persistence.persist_profile` (F1.10, com escopo BR/F2.13) +
  `agents.persistence.persist_score`/`persist_recommendations` (F4.7/F6.13), idempotentes.

**Política de HITL em lote (decisão travada, F1.14):** runs batch rodam com `hitl=AUTO` — o
interrupt humano (F2.8) **não** bloqueia a fila; empresa de baixa confiança cai no estado
terminal (F2.12 `INSUFFICIENT_DATA`) ou non-AI de alta confiança (F2.13 `OUT_OF_SCOPE`) e é
marcada p/ revisão assíncrona. HITL síncrono fica só no single-company lookup.

**Núcleo testável offline:** `candidate_domains` (extração pura dos links de saída) e o laço
`build_cohort` (com `runner`/`session_factory` injetados) rodam sem rede nem reactor Twisted;
o crawl real (F1.6) e o pipeline real (F2) entram por injeção/flag.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from packages.agents.persistence import persist_recommendations, persist_score
from packages.schemas.enums import ExecutionMode, HITLMode, RunStatus
from packages.scraping.persistence import persist_profile

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from sqlmodel import Session

    from packages.schemas.state import GraphState
    from packages.scraping.crawler import CrawledPage
    from packages.scraping.seeds import Source

    SessionFactory = Callable[[], Session]
    Runner = Callable[..., GraphState]

# Hosts que NUNCA são empresa candidata (redes sociais, vídeo, infra, agregadores): um
# link p/ esses domínios é navegação/social, não a home de uma startup a perfilar.
_NON_COMPANY_HOSTS: frozenset[str] = frozenset(
    {
        "facebook.com", "instagram.com", "twitter.com", "x.com", "linkedin.com",
        "youtube.com", "youtu.be", "tiktok.com", "wa.me", "whatsapp.com",
        "google.com", "goo.gl", "apple.com", "play.google.com", "github.com",
        "medium.com", "t.me", "telegram.me", "pinterest.com", "spotify.com",
        "vimeo.com", "flickr.com", "soundcloud.com", "example.com",
    }
)

# Estados terminais que marcam a candidata p/ revisão assíncrona (não bloqueiam a fila).
_REVIEW_STATUSES: frozenset[RunStatus] = frozenset(
    {RunStatus.INSUFFICIENT_DATA, RunStatus.AWAITING_REVIEW, RunStatus.OUT_OF_SCOPE}
)


# --- modelos (tipados, auditáveis) -------------------------------------------


class CohortCandidate(BaseModel):
    """Uma startup candidata derivada do crawl (F1.6) — unidade da fila (F1.14)."""

    domain: str = Field(description="Domínio registrável da empresa (host normalizado).")
    query: str = Field(description="Consulta passada ao `run_pipeline` (URL da home).")
    name: str = Field(default="", description="Texto-âncora do link (pista do nome).")
    source_id: str = Field(default="", description="Fonte §9 que descobriu a candidata.")


class CohortOutcome(BaseModel):
    """Resultado de perfilar **uma** candidata no lote (auditável).

    `error` carrega **só falha de verdade** (runner/persistência estourou); resultado
    terminal legítimo (fora de escopo, sem perfil) fica em `status`/`needs_review`, não em
    `error`, p/ não inflar a contagem de erros.
    """

    query: str
    domain: str
    run_id: str | None = None
    company_id: int | None = None
    status: RunStatus = RunStatus.PENDING
    needs_review: bool = False
    evidence_count: int = 0
    error: str | None = None

    @property
    def persisted(self) -> bool:
        """True se a empresa entrou na tabela `company` (perfil em escopo)."""
        return self.company_id is not None


class CohortReport(BaseModel):
    """Relatório do lote — o que entrou na coorte e o que caiu p/ revisão."""

    outcomes: list[CohortOutcome] = Field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.outcomes)

    @property
    def persisted(self) -> list[CohortOutcome]:
        """Empresas acumuladas na `company` (alimentam F6.5–F6.7 e F7.1)."""
        return [o for o in self.outcomes if o.persisted]

    @property
    def needs_review(self) -> list[CohortOutcome]:
        """Marcadas p/ revisão assíncrona (baixa confiança / fora de escopo)."""
        return [o for o in self.outcomes if o.needs_review or o.status in _REVIEW_STATUSES]

    @property
    def errored(self) -> list[CohortOutcome]:
        """Falharam de fato (runner/persistência estourou) — não envenenam o resto."""
        return [o for o in self.outcomes if o.error is not None]


# --- descoberta de candidatas (puro, offline) --------------------------------


# Seed de candidatas curadas (F7.1): fallback robusto quando o crawl-discovery rende 0 ao vivo.
_CANDIDATES_SEED = Path(__file__).resolve().parents[2] / "data" / "seeds" / "cohort_candidates.yaml"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "empresa"


def _strip_www(host: str) -> str:
    host = host.lower()
    return host[4:] if host.startswith("www.") else host


def _registrable_host(url: str) -> str:
    """Host registrável (sem `www.`) de uma URL; vazio se não der p/ parsear."""
    return _strip_www(urlparse(url).netloc)


def _is_non_company(host: str) -> bool:
    """True se o host é (ou é subdomínio de) um host de não-empresa da denylist."""
    return any(host == nc or host.endswith("." + nc) for nc in _NON_COMPANY_HOSTS)


def candidate_domains(
    pages: Iterable[CrawledPage], *, seed_hosts: Iterable[str] = ()
) -> tuple[CohortCandidate, ...]:
    """Extrai startups candidatas dos links de saída das páginas crawladas (F1.6 → F1.14).

    Candidata = link p/ um domínio **externo** aos hosts das seeds (o portfólio aponta p/ os
    sites das startups) e fora da denylist de não-empresa (redes sociais/infra). O próprio
    host da página também é excluído (links internos do portfólio). Dedup por domínio
    registrável, preservando a ordem de descoberta. **Puro**: não toca rede.
    """
    seeds = {_strip_www(h) for h in seed_hosts}
    seen: set[str] = set()
    out: list[CohortCandidate] = []
    for page in pages:
        page_host = _registrable_host(page.url)
        for link in page.links:
            host = _registrable_host(link.url)
            if not host or host in seen:
                continue
            if host == page_host or host in seeds or any(host.endswith("." + s) for s in seeds):
                continue  # link interno do portfólio/seed
            if _is_non_company(host):
                continue  # rede social / infra — não é startup
            seen.add(host)
            out.append(
                CohortCandidate(
                    domain=host,
                    query=f"https://{host}",
                    name=link.text.strip()[:120],
                    source_id=page.source_id,
                )
            )
    return tuple(out)


def discover_candidates(
    *,
    sources: Sequence[Source] | None = None,
    crawl_fn: Callable[..., Sequence[CrawledPage]] | None = None,
    max_pages: int = 50,
    max_depth: int = 2,
) -> tuple[CohortCandidate, ...]:
    """Crawla as seeds `allow` de descoberta e extrai as candidatas (F1.14).

    `sources` default = portfólios/programas + notícias `allow` (§9.2), pulando o placeholder
    `official-channels`. `crawl_fn` é **injetável** (offline/teste); default = o crawler
    Scrapy real (F1.6), import preguiçoso pois sobe o reactor do Twisted (bloqueante, um por
    processo). Devolve a fila de candidatas (vazia se nenhuma seed coletável).
    """
    from packages.scraping.seeds import allowlist

    if sources is not None:
        srcs = tuple(sources)
    else:
        srcs = tuple(
            s
            for s in allowlist()
            if s.type in ("program", "news") and _strip_www(urlparse(s.url).netloc) != "example.com"
        )
    if not srcs:
        return ()
    if crawl_fn is None:
        from packages.scraping.crawler import crawl as crawl_fn  # lazy: Twisted só no real

    pages = crawl_fn(srcs, max_pages=max_pages, max_depth=max_depth)
    seed_hosts = [urlparse(s.url).netloc.lower() for s in srcs]
    return candidate_domains(pages, seed_hosts=seed_hosts)


def candidates_from_seed(path: Path | None = None) -> tuple[CohortCandidate, ...]:
    """Lê candidatas curadas de `data/seeds/cohort_candidates.yaml` (F7.1).

    Fallback **robusto** à descoberta por crawl (que rende 0 ao vivo: robots/JS/bloqueio):
    nomes de empresas BR de IA **reais**, que o pipeline resolve e **verifica ao vivo** (Tavily
    pelo `query` → Firecrawl). `query` é o termo de busca; `domain` é um slug do nome (o domínio
    real vem do perfil resolvido na persistência). Empresa que não rende perfil é pulada (honesto).
    """
    import yaml

    src = path or _CANDIDATES_SEED
    data = yaml.safe_load(src.read_text(encoding="utf-8")) or {}
    out: list[CohortCandidate] = []
    for raw in data.get("candidates", []):
        name = raw["name"]
        out.append(
            CohortCandidate(
                domain=raw.get("domain", _slug(name)),
                query=raw.get("query", name),
                name=name,
                source_id="cohort-seed",
            )
        )
    return tuple(out)


# --- laço em lote ------------------------------------------------------------


def build_cohort(
    candidates: Sequence[CohortCandidate],
    *,
    session_factory: SessionFactory,
    runner: Runner | None = None,
    hitl: HITLMode = HITLMode.AUTO,
    limit: int | None = None,
) -> CohortReport:
    """Roda o pipeline (F2) por candidata e acumula na tabela `company` (F1.14).

    `runner` default = `run_pipeline` (real atrás de `scraper_use_network`); **injetável** p/
    teste. `session_factory` abre uma sessão **fresca por empresa** — isola a transação, então
    a falha de uma candidata não envenena as outras (continue-on-error). `hitl=AUTO`: o
    interrupt (F2.8) não bloqueia; baixa confiança (F2.12) / non-AI (F2.13) caem em estado
    terminal e são marcadas p/ revisão. Devolve o `CohortReport` auditável.
    """
    if runner is None:
        from packages.agents.graph import run_pipeline as runner

    selected = list(candidates)[:limit] if limit is not None else list(candidates)
    outcomes = [
        _profile_one(cand, runner=runner, session_factory=session_factory, hitl=hitl)
        for cand in selected
    ]
    return CohortReport(outcomes=outcomes)


def _profile_one(
    cand: CohortCandidate, *, runner: Runner, session_factory: SessionFactory, hitl: HITLMode
) -> CohortOutcome:
    """Perfila uma candidata e persiste; qualquer exceção vira `error` (não derruba o lote)."""
    try:
        state = runner(cand.query, mode=ExecutionMode.SINGLE_COMPANY, hitl=hitl)
    except Exception as exc:  # noqa: BLE001 — continue-on-error é o contrato do lote
        return CohortOutcome(
            query=cand.query, domain=cand.domain, error=f"run falhou ({type(exc).__name__}: {exc})"
        )
    return _persist_state(state, cand, session_factory=session_factory)


def _persist_state(
    state: GraphState, cand: CohortCandidate, *, session_factory: SessionFactory
) -> CohortOutcome:
    """Acumula um run perfilado na `company` (perfil + score + recomendações), idempotente."""
    evidence_count = len(state.raw_docs)
    # Sem perfil extraído (coleta vazia) → terminal, marca p/ revisão, não entra na company.
    if state.profile is None:
        return CohortOutcome(
            query=cand.query, domain=cand.domain, run_id=state.run_id,
            status=state.status, needs_review=True, evidence_count=evidence_count,
        )
    try:
        with session_factory() as session:
            company = persist_profile(
                session, state.profile, run_id=state.run_id, enforce_scope=True
            )
            if company is None:
                # fora do escopo BR / non-AI (F2.13): não acumula, marca p/ revisão.
                return CohortOutcome(
                    query=cand.query, domain=cand.domain, run_id=state.run_id,
                    status=RunStatus.OUT_OF_SCOPE, needs_review=True,
                    evidence_count=evidence_count,
                )
            company_id = company.id
            if state.aimi is not None:
                persist_score(session, state.aimi, company_id=company_id, run_id=state.run_id)
            if state.recommendations:
                persist_recommendations(
                    session, state.recommendations, company_id=company_id, run_id=state.run_id
                )
            session.commit()
    except Exception as exc:  # noqa: BLE001 — falha de persistência não derruba o lote
        return CohortOutcome(
            query=cand.query, domain=cand.domain, run_id=state.run_id,
            status=state.status, evidence_count=evidence_count,
            error=f"persistência falhou ({type(exc).__name__}: {exc})",
        )
    return CohortOutcome(
        query=cand.query, domain=cand.domain, run_id=state.run_id, company_id=company_id,
        status=state.status, needs_review=state.needs_review, evidence_count=evidence_count,
    )


# --- CLI ---------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    """CLI do cohort builder (F1.14).

    Descobre candidatas das seeds `allow` (crawl real F1.6) e perfila em lote, acumulando na
    `company`. **Real** exige `SCRAPER_USE_NETWORK=true` (+ flags de LLM p/ classe/AIMI reais);
    sem elas o scraper é no-op e os perfis saem vazios. `--db sqlite:///data/cohort.db` roda
    sem Postgres (F0.2 adiado); `--dry-run` só lista as candidatas (sem rede de pipeline).
    """
    parser = argparse.ArgumentParser(description="Cohort builder — sourcing em lote (F1.14).")
    parser.add_argument("--db", default=None, help="URL do banco (default = settings.postgres).")
    parser.add_argument("--limit", type=int, default=None, help="Máx. de empresas a perfilar.")
    parser.add_argument("--max-pages", type=int, default=50, help="Páginas por crawl (F1.6).")
    parser.add_argument("--max-depth", type=int, default=2, help="Profundidade do crawl.")
    parser.add_argument(
        "--seed", action="store_true", help="Usa as candidatas curadas da seed (F7.1)."
    )
    parser.add_argument(
        "--candidates", default=None, help="YAML de candidatas curadas (implica --seed)."
    )
    parser.add_argument("--dry-run", action="store_true", help="Só lista candidatas, não perfila.")
    args = parser.parse_args(argv)

    if args.candidates is not None:
        candidates = candidates_from_seed(Path(args.candidates))
    elif args.seed:
        candidates = candidates_from_seed()
    else:
        candidates = discover_candidates(max_pages=args.max_pages, max_depth=args.max_depth)
    print(f"candidatas: {len(candidates)}")
    if args.dry_run:
        for c in candidates[: args.limit or len(candidates)]:
            print(f"  {c.domain}  ({c.source_id})  {c.name!r}")
        return 0

    from sqlmodel import Session, SQLModel, create_engine

    from packages.db.engine import get_engine

    engine = create_engine(args.db) if args.db else get_engine()
    SQLModel.metadata.create_all(engine)  # garante o schema (sqlite novo); no-op se já existe
    report = build_cohort(candidates, session_factory=lambda: Session(engine), limit=args.limit)

    print(
        f"perfiladas: {report.total} | na coorte: {len(report.persisted)} | "
        f"revisão: {len(report.needs_review)} | erro: {len(report.errored)}"
    )
    for o in report.outcomes:
        flag = "ok" if o.persisted else ("ERRO" if o.error else "revisão")
        extra = f" :: {o.error}" if o.error else ""
        print(f"  [{flag}] {o.domain} status={o.status.value} ev={o.evidence_count}{extra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
