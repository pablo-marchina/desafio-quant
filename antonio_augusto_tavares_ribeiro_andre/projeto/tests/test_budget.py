"""Testes da guarda de orçamento de LLM por run (F2.11).

Tudo offline/determinista (sem rede/LLM). Exercita:
- `LLMBudget.check`: motivo do estouro por chamadas/tokens/custo, `None` sob o teto, `is_unbounded`;
- `budget_from_settings`: off por default, liga com teto, `None` quando ligado sem nenhum teto;
- `BudgetGuard`: no-op fora de escopo/sem budget, libera sob o teto, **aborta** (`BudgetExceeded`)
  ao atingir o teto, em `on_chat_model_start` e `on_llm_start`, com `raise_error=True`;
- integração com `run_pipeline`/`stream_pipeline`: um nó "guloso" (simula chamadas de LLM atrás
  do guard) tem as chamadas **limitadas** pelo teto, o run segue sem travar e o estado ganha
  `trace["budget"]` + nota em `errors`; sem estouro só carimba `usage`; offline não gera nada.
"""

from __future__ import annotations

import pytest

from packages.agents import run_pipeline, stream_pipeline
from packages.config import get_settings
from packages.observability.cost import (
    BUDGET_GUARD,
    BudgetExceeded,
    LLMBudget,
    TokenUsage,
    budget_from_settings,
    capture_usage,
    record_usage,
)

_SUPER = "nvidia/llama-3.3-nemotron-super-49b-v1"
_NANO = "nvidia/llama-3.1-nemotron-nano-8b-v1"


# --- LLMBudget.check ----------------------------------------------------------


def test_budget_check_none_under_all_limits() -> None:
    budget = LLMBudget(max_calls=5, max_tokens=1000, max_cost_usd=1.0)
    assert budget.check(TokenUsage(calls=1, total_tokens=10, cost_usd=0.01)) is None


def test_budget_check_calls_reached() -> None:
    reason = LLMBudget(max_calls=2).check(TokenUsage(calls=2))
    assert reason is not None and "chamadas 2/2" in reason


def test_budget_check_tokens_reached() -> None:
    reason = LLMBudget(max_tokens=100).check(TokenUsage(total_tokens=120))
    assert reason is not None and "tokens 120/100" in reason


def test_budget_check_cost_reached() -> None:
    reason = LLMBudget(max_cost_usd=0.5).check(TokenUsage(cost_usd=0.5))
    assert reason is not None and "custo" in reason


def test_budget_unbounded() -> None:
    assert LLMBudget().is_unbounded is True
    assert LLMBudget(max_calls=1).is_unbounded is False


# --- budget_from_settings -----------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_budget_from_settings_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_BUDGET_ENABLED", raising=False)
    get_settings.cache_clear()
    assert budget_from_settings() is None


def test_budget_from_settings_enabled_with_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BUDGET_ENABLED", "true")
    monkeypatch.setenv("LLM_MAX_CALLS", "7")
    get_settings.cache_clear()
    budget = budget_from_settings()
    assert budget is not None
    assert budget.max_calls == 7
    assert budget.max_tokens is None  # 0 no settings → sem teto naquela dimensão


def test_budget_from_settings_enabled_without_any_cap_is_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Ligado mas sem nenhum teto definido equivale a não ter guarda (None).
    monkeypatch.setenv("LLM_BUDGET_ENABLED", "true")
    monkeypatch.setenv("LLM_MAX_CALLS", "0")
    monkeypatch.setenv("LLM_MAX_TOKENS", "0")
    monkeypatch.setenv("LLM_MAX_COST_USD", "0")
    get_settings.cache_clear()
    assert budget_from_settings() is None


# --- BudgetGuard --------------------------------------------------------------


def test_budget_guard_raise_error_is_true() -> None:
    # raise_error=True faz o LangChain PROPAGAR a exceção (em vez de só logar) e abortar a chamada.
    assert BUDGET_GUARD.raise_error is True


def test_budget_guard_noop_without_scope() -> None:
    # Fora de um capture_usage não há budget no contexto → nunca barra.
    BUDGET_GUARD.on_chat_model_start({}, [])


def test_budget_guard_allows_under_budget() -> None:
    with capture_usage(budget=LLMBudget(max_calls=2)):
        record_usage(TokenUsage.for_call(model=_NANO, input_tokens=1, output_tokens=1))
        BUDGET_GUARD.on_chat_model_start({}, [])  # total.calls=1 < 2 → libera


def test_budget_guard_blocks_when_calls_reached() -> None:
    with capture_usage(budget=LLMBudget(max_calls=1)):
        record_usage(TokenUsage.for_call(model=_NANO, input_tokens=1, output_tokens=1))
        with pytest.raises(BudgetExceeded):
            BUDGET_GUARD.on_chat_model_start({}, [])


def test_budget_guard_blocks_on_llm_start_by_tokens() -> None:
    with capture_usage(budget=LLMBudget(max_tokens=10)):
        record_usage(TokenUsage.for_call(model=_NANO, input_tokens=8, output_tokens=5))  # 13 ≥ 10
        with pytest.raises(BudgetExceeded):
            BUDGET_GUARD.on_llm_start({}, [])


# --- integração com run_pipeline / stream_pipeline ----------------------------


def _greedy_node(calls: list[int]):
    """Nó que simula chamadas de LLM atrás do guard até ser barrado (como faria a rede real)."""

    def node(state):  # noqa: ANN001, ANN202
        for _ in range(5):
            try:
                BUDGET_GUARD.on_chat_model_start({}, [])
            except BudgetExceeded:
                break
            record_usage(TokenUsage.for_call(model=_SUPER, input_tokens=100, output_tokens=50))
            calls[0] += 1
        return {}

    return node


def test_run_pipeline_budget_caps_calls_and_stamps_note(monkeypatch: pytest.MonkeyPatch) -> None:
    from packages.agents import nodes

    calls = [0]
    monkeypatch.setitem(nodes.NODES, "classifier", _greedy_node(calls))

    out = run_pipeline("Acme AI", run_id="run-budget-1", budget=LLMBudget(max_calls=2))

    assert calls[0] == 2  # o guard barrou a 3ª chamada (poupa o free tier)
    assert out.trace["usage"]["calls"] == 2
    assert out.trace["budget"]["limited"] is True
    assert "chamadas 2/2" in out.trace["budget"]["reason"]
    assert any("orcamento de LLM atingido" in e for e in out.errors)


def test_run_pipeline_budget_not_hit_only_stamps_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    from packages.agents import nodes

    calls = [0]
    monkeypatch.setitem(nodes.NODES, "classifier", _greedy_node(calls))

    out = run_pipeline("Acme AI", run_id="run-budget-2", budget=LLMBudget(max_calls=10))

    assert calls[0] == 5  # teto folgado → o nó faz todas as chamadas
    assert out.trace["usage"]["calls"] == 5
    assert "budget" not in out.trace  # sem estouro, sem nota
    assert not any("orcamento" in e for e in out.errors)


def test_run_pipeline_offline_with_budget_stamps_nothing() -> None:
    # Espinha offline (sem LLM) → nenhuma chamada, então nem usage nem budget (M2/DoD).
    out = run_pipeline("Acme AI", run_id="run-budget-3", budget=LLMBudget(max_calls=1))
    assert "usage" not in out.trace
    assert "budget" not in out.trace


def test_stream_pipeline_budget_caps_and_stamps(monkeypatch: pytest.MonkeyPatch) -> None:
    from packages.agents import nodes

    calls = [0]
    monkeypatch.setitem(nodes.NODES, "classifier", _greedy_node(calls))

    out = stream_pipeline("Acme AI", run_id="run-budget-4", budget=LLMBudget(max_calls=2))

    assert calls[0] == 2
    assert out.trace["budget"]["limited"] is True
    assert any("orcamento de LLM atingido" in e for e in out.errors)
