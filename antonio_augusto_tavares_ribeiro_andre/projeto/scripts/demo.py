"""Demo executável do TAPI — NVIDIA Startup AI Radar (F7.7).

Mostra o produto funcionando. Dois modos, escolhidos por flag:

    python scripts/demo.py            # OFFLINE (default): espinha verde, sem rede/credencial
    python scripts/demo.py --real     # E2E REAL: Tavily+Firecrawl+Nemotron+RAG — exige .env

**Offline** (reproduzível por qualquer um, é o que roda no CI) faz duas coisas honestas:

  (1) **Grafo ponta a ponta** — roda o pipeline LangGraph (10 nós, ARQUITETURA §3) sobre uma
      consulta. Sem rede o scraper é um no-op, então o run **termina sem perfil**: o TAPI
      **não inventa empresa** (anti-alucinação, o princípio do projeto), ele para honesto.

  (2) **Briefing completo determinista** — monta o artefato que o gerente lê (diagnóstico AIMI →
      recomendações com **evidência dos dois lados** → briefing executivo) a partir de um caso
      **rotulado** do eval set (F1.12), pela mesma espinha que F7.2b/F7.2c medem offline. É o
      output real do produto, sem chamar LLM/rede.

**Real** liga as flags de rede/LLM (`scraper_use_network`, `*_use_llm`, embeddings/Qdrant/rerank),
exige as chaves no `.env` (NVIDIA/Tavily/Firecrawl) e roda o grafo de verdade sobre a consulta —
o caminho do run e2e da Hand Talk. Degrada honesto se faltar chave.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

# Permite `python scripts/demo.py` da raiz do repo (a raiz não entra no sys.path sozinha quando
# o script é chamado pelo caminho; espelha o `pythonpath=["."]` que o pytest usa, ver pyproject).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Flags que ligam o caminho real no grafo (uma por nó/recurso — ver packages/config/settings.py).
# Setadas no ambiente ANTES de instanciar o Settings (que é @lru_cache); por isso o import dos
# pacotes é preguiçoso (dentro das funções) e o --real limpa o cache antes de rodar.
_REAL_FLAGS = (
    "SCRAPER_USE_NETWORK",
    "PLANNER_USE_LLM",
    "EXTRACTOR_USE_LLM",
    "CLASSIFIER_USE_LLM",
    "RECOMMENDER_USE_LLM",
    "BRIEFING_USE_LLM",
    "EMBEDDINGS_USE_NV",
    "INDEX_USE_QDRANT",
    "RERANKER_USE_NV",
)

_DEFAULT_QUERY = "Hand Talk tradutor de Libras com inteligência artificial"


def _rule(title: str) -> None:
    print(f"\n{'=' * 78}\n  {title}\n{'=' * 78}")


def _evidence_line(evidencias: Sequence[object]) -> str:
    """Primeira URL de uma lista de Evidence (ou '—' se vazia)."""
    for ev in evidencias:
        url = getattr(ev, "url", None)
        if url:
            return str(url)
    return "—"


# --- (1) grafo offline -------------------------------------------------------


def demo_graph(query: str) -> None:
    """Roda o pipeline LangGraph offline e mostra o backbone + plano + terminal honesto."""
    from packages.agents import PIPELINE, run_pipeline

    _rule("1) PIPELINE LANGGRAPH (espinha offline — sem rede)")
    print("Backbone (ARQUITETURA §3):")
    print("   " + " → ".join(PIPELINE))
    print(f"\nConsulta: {query!r}")

    state = run_pipeline(query)

    print(f"\nPlano de coleta (search_planner, determinista): {len(state.sources)} fontes")
    for term in state.search_terms[:3]:
        print(f"   • {term}")
    print(f"\nstatus={state.status.value}  perfil={'sim' if state.profile else 'não'}  "
          f"docs={len(state.raw_docs)}  recomendações={len(state.recommendations)}")
    print(
        "\nLeitura: offline o scraper não acessa a rede → 0 documentos → SEM perfil. O grafo\n"
        "roda inteiro mas o TAPI não fabrica uma empresa que não coletou (anti-alucinação).\n"
        "Para o briefing real desta consulta, rode com --real (exige chaves no .env)."
    )


# --- (2) briefing offline completo ------------------------------------------


def demo_offline_briefing(case: str | None) -> None:
    """Monta um briefing COMPLETO pela espinha determinista a partir de um caso rotulado."""
    from packages.agents import make_briefing, make_recommendations
    from packages.eval.aimi_correlation import profile_for
    from packages.eval.dataset import load_eval_set
    from packages.eval.recommend_cases import full_recall_retrieval
    from packages.eval.recommendation_metrics import aimi_from_labels

    entries = load_eval_set()
    if case:
        entry = next((e for e in entries if e.id == case), None)
        if entry is None:
            sys.exit(f"caso {case!r} não encontrado no eval set (use --list para ver os IDs).")
    else:  # default: uma AI-native alvo_graduacao — a coorte que importa pro Inception (F6.13)
        entry = next(e for e in entries if e.region.value == "alvo_graduacao")

    aimi = aimi_from_labels(entry)
    profile = profile_for(entry)
    recs = make_recommendations(aimi, profile, full_recall_retrieval())
    briefing = make_briefing(aimi, profile, recs, empresa=entry.nome)

    _rule(f"2) BRIEFING COMPLETO (espinha determinista, offline) — {entry.nome}")
    print(f"Caso rotulado: {entry.id}  ·  {entry.setor}  ·  {entry.pais}")
    print(f"\nDIAGNÓSTICO  classe={aimi.classificacao.value}  AIMI={aimi.total}/100  "
          f"região={entry.region.value}  inception_priority={briefing.inception_priority}")
    for pilar in (aimi.data_moat, aimi.workflow_depth, aimi.technical_optimization,
                  aimi.distribution_moat):
        nome = getattr(pilar.pilar, "value", pilar.pilar)
        band = getattr(pilar.band, "value", pilar.band)
        print(f"   {nome:<24} {pilar.score:>2}/25  ({band})")

    print(f"\nRECOMENDAÇÕES NVIDIA: {len(recs)} (top 3, com evidência dos dois lados)")
    for r in recs[:3]:
        print(f"   ▸ {r.tech}  [prio={r.prioridade.value}, complex={r.complexidade.value}]")
        print(f"       gap startup : {_evidence_line(r.evidencia_gap)}")
        print(f"       fonte NVIDIA: {_evidence_line(r.evidencia_nvidia)}")

    _rule("BRIEFING EXECUTIVO (o que o gerente lê)")
    print("» Resumo executivo:\n  " + briefing.resumo_executivo.strip())
    print("\n» Ação comercial:\n  " + briefing.acao_comercial.strip())
    print("\n» Ação técnica:\n  " + briefing.acao_tecnica.strip())
    print("\n» Ação comunitária:\n  " + briefing.acao_comunitaria.strip())
    print(
        "\nTudo acima é determinista (sem LLM/rede): diagnóstico e recomendações nunca vêm do\n"
        "modelo (anti-alucinação); o --real deixa o Nemotron-Super refinar só a REDAÇÃO, ancorado."
    )


def list_cases() -> None:
    """Lista os IDs do eval set (para escolher um caso com --case)."""
    from packages.eval.dataset import load_eval_set

    _rule("Casos do eval set (F1.12) — use --case <id>")
    for e in load_eval_set():
        print(f"   {e.id:<18} {e.classificacao.value:<11} {e.region.value:<16} {e.nome}")


# --- (3) e2e real ------------------------------------------------------------


def demo_real(query: str) -> None:
    """Liga as flags de rede/LLM e roda o grafo de verdade sobre a consulta (exige .env)."""
    for flag in _REAL_FLAGS:
        os.environ[flag] = "true"

    from packages.agents import run_pipeline
    from packages.config import get_settings

    get_settings.cache_clear()  # reaproveita o cache offline → relê o ambiente já com as flags
    s = get_settings()
    faltando = [
        name for name, val in (
            ("NVIDIA_API_KEY", s.nvidia_api_key),
            ("TAVILY_API_KEY", s.tavily_api_key),
            ("FIRECRAWL_API_KEY", s.firecrawl_api_key),
        ) if not val
    ]
    if faltando:
        sys.exit(
            "Modo --real exige chaves no .env: faltam " + ", ".join(faltando) + ".\n"
            "Copie .env.example → .env e preencha (build.nvidia.com / tavily.com / firecrawl.dev)."
        )

    _rule("E2E REAL — Tavily + Firecrawl + Nemotron-Super + RAG")
    print(f"Consulta: {query!r}")
    print("(coleta ao vivo + diagnóstico + RAG + briefing — pode levar minutos)")
    state = run_pipeline(query)

    if state.profile is None:
        print(f"\nstatus={state.status.value} — evidência insuficiente, terminou sem perfil.")
        for err in state.errors[:5]:
            print(f"   ! {err}")
        return

    p, aimi, brief = state.profile, state.aimi, state.briefing
    print(f"\nPERFIL: {p.nome}  ·  classe={getattr(p, 'classificacao', '—')}")
    if aimi:
        print(f"AIMI={aimi.total}/100  ·  recomendações={len(state.recommendations)}")
    if brief:
        print("\n» Resumo executivo:\n  " + brief.resumo_executivo.strip())
    usage = (state.trace or {}).get("usage")
    if usage:
        print(f"\nuso de LLM (F2.9): {usage}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Demo do TAPI (F7.7).")
    parser.add_argument("--real", action="store_true", help="E2E real (rede/LLM; exige .env).")
    parser.add_argument("--query", default=_DEFAULT_QUERY, help="Consulta da startup.")
    parser.add_argument("--case", default=None, help="ID do eval set p/ o briefing offline (2).")
    parser.add_argument("--list", action="store_true", help="Lista os casos do eval set e sai.")
    args = parser.parse_args(argv)

    if args.list:
        list_cases()
        return 0
    if args.real:
        demo_real(args.query)
        return 0

    print("TAPI — demo OFFLINE (espinha verde, sem rede/credencial). --real p/ o e2e completo.")
    demo_graph(args.query)
    demo_offline_briefing(args.case)
    print("\nMétricas de qualidade consolidadas: docs/ARQUITETURA.md §9 (reprodução no README).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
