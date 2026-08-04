"""Testes do nó search_planner (F2.3).

Tudo offline/determinista (o caminho LLM é opt-in via `planner_use_llm` + chave):
- detecção de modo (single-company vs discovery por setor/região);
- plano determinista por modo (termos + fontes §9, com a query sempre 1ª);
- parsing do JSON do Nano (prompt v1) em `SearchPlan` tipado;
- o nó devolve update parcial coerente (RUNNING + modo + termos + fontes).
"""

from __future__ import annotations

import packages.agents.search_planner as sp
from packages.agents.search_planner import (
    PrioritizedSource,
    SearchPlan,
    detect_mode,
    deterministic_plan,
    make_plan,
    resolve_mode,
    search_planner,
)
from packages.schemas import ExecutionMode, GraphState, RunStatus


def test_detect_mode_company_name_is_single() -> None:
    assert detect_mode("Acme AI") is ExecutionMode.SINGLE_COMPANY
    assert detect_mode("Nubank") is ExecutionMode.SINGLE_COMPANY


def test_detect_mode_domain_is_single() -> None:
    assert detect_mode("acme.ai") is ExecutionMode.SINGLE_COMPANY
    assert detect_mode("https://openai.com/about") is ExecutionMode.SINGLE_COMPANY


def test_detect_mode_sector_query_is_discovery() -> None:
    assert detect_mode("fintechs AI em SP") is ExecutionMode.DISCOVERY
    assert detect_mode("startups de saúde com IA") is ExecutionMode.DISCOVERY
    assert detect_mode("healthtechs no Brasil") is ExecutionMode.DISCOVERY


def test_detect_mode_empty_is_single() -> None:
    assert detect_mode("   ") is ExecutionMode.SINGLE_COMPANY


def test_resolve_mode_honors_explicit_discovery() -> None:
    # caller declarou discovery p/ um nome ambíguo → respeitado, não rebaixado.
    assert resolve_mode("Acme AI", ExecutionMode.DISCOVERY) is ExecutionMode.DISCOVERY


def test_resolve_mode_detects_from_default() -> None:
    resolved = resolve_mode("fintechs AI em SP", ExecutionMode.SINGLE_COMPANY)
    assert resolved is ExecutionMode.DISCOVERY


def test_single_company_plan_has_query_first_and_sources() -> None:
    plan = deterministic_plan("Acme AI", ExecutionMode.SINGLE_COMPANY)
    assert isinstance(plan, SearchPlan)
    assert plan.mode is ExecutionMode.SINGLE_COMPANY
    assert plan.search_terms[0] == "Acme AI"
    kinds = {s.kind for s in plan.sources}
    assert "official_site" in kinds  # site oficial é o alvo de maior sinal (F1.15)
    # notícias §9.2 (allow) entram como cobertura, com URL http.
    assert any(s.kind == "news" and s.query_or_url.startswith("http") for s in plan.sources)


def test_domain_query_derives_company_label() -> None:
    plan = deterministic_plan("acme.ai", ExecutionMode.SINGLE_COMPANY)
    assert plan.search_terms[0] == "acme.ai"  # query crua continua 1ª
    assert any("acme" in s.query_or_url for s in plan.sources)


def test_discovery_plan_biases_terms_and_lists_seed_sources() -> None:
    plan = deterministic_plan("fintechs AI em SP", ExecutionMode.DISCOVERY)
    assert plan.mode is ExecutionMode.DISCOVERY
    assert plan.search_terms[0] == "fintechs AI em SP"  # bias_query mantém a original 1ª
    assert len(plan.search_terms) > 1  # variantes enviesadas por sinais AI-native (F1.11)
    kinds = {s.kind for s in plan.sources}
    assert {"program", "directory"} & kinds  # superfícies de descoberta §9 (F1.14)
    # nenhuma fonte deny (ex.: StartSe) vaza para o plano (política F1.15).
    assert all(s.query_or_url for s in plan.sources)


def test_deny_directory_not_in_discovery_sources() -> None:
    urls = {s.query_or_url for s in deterministic_plan("fintechs", ExecutionMode.DISCOVERY).sources}
    assert not any("startse" in u for u in urls)


def test_source_values_dedup_preserves_order() -> None:
    plan = SearchPlan(
        mode=ExecutionMode.DISCOVERY,
        sources=[
            PrioritizedSource(kind="news", query_or_url="https://a.com"),
            PrioritizedSource(kind="news", query_or_url="https://a.com"),
            PrioritizedSource(kind="program", query_or_url="https://b.com"),
        ],
    )
    assert plan.source_values == ["https://a.com", "https://b.com"]


def test_parse_plan_from_nano_json() -> None:
    raw = """Plano:
    ```json
    {
      "search_terms": ["Acme AI", "Acme inteligência artificial"],
      "prioritized_sources": [
        {"type": "official_site", "query_or_url": "Acme site oficial"},
        {"type": "weird", "query_or_url": "Acme news"},
        {"type": "news", "query_or_url": ""}
      ],
      "notes": "BR"
    }
    ```"""
    plan = sp._parse_plan(raw, mode=ExecutionMode.SINGLE_COMPANY)
    assert plan.search_terms == ["Acme AI", "Acme inteligência artificial"]
    assert [s.query_or_url for s in plan.sources] == ["Acme site oficial", "Acme news"]
    assert plan.sources[1].kind == "search"  # tipo desconhecido → 'search'
    assert plan.notes == "BR"


def test_make_plan_offline_is_deterministic(monkeypatch) -> None:
    # sem flag/chave → caminho determinista, sem tocar a rede.
    monkeypatch.setattr(sp, "get_settings", lambda: _FakeSettings(use_llm=True, key=""))
    plan = make_plan("Acme AI", ExecutionMode.SINGLE_COMPANY)
    assert plan.search_terms[0] == "Acme AI"
    assert plan.source_values


def test_node_returns_partial_update(monkeypatch) -> None:
    monkeypatch.setattr(sp, "get_settings", lambda: _FakeSettings(use_llm=False, key=""))
    state = GraphState(run_id="r1", query="fintechs AI em SP")
    update = search_planner(state)
    assert update["status"] is RunStatus.RUNNING
    assert update["mode"] is ExecutionMode.DISCOVERY  # detectado da query
    assert update["search_terms"][0] == "fintechs AI em SP"
    assert update["sources"]


class _FakeSettings:
    def __init__(self, *, use_llm: bool, key: str) -> None:
        self.planner_use_llm = use_llm
        self.nvidia_api_key = key
