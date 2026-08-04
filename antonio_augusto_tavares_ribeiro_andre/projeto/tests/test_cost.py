"""Testes da contabilidade de tokens/custo (F2.9).

Tudo offline/determinista (sem Langfuse nem LLM). Exercita:
- `estimate_cost`: tabela por substring, default p/ desconhecido, saída-0 das embeddings;
- `TokenUsage`: merge (agregação) e `for_call` (custo de uma chamada);
- `extract_usage`: lê os dois formatos (`usage_metadata` do LangChain e `token_usage` OpenAI-like)
  e conta calls=1 mesmo sem tokens reportados;
- `capture_usage`/`record_usage`: acumulam no escopo e são no-op fora dele;
- `UsageRecorder.on_llm_end`: mede uma chamada dentro do escopo;
- `run_pipeline`: offline não gera uso (trace intacto); com uso registrado, carimba
  `trace["usage"]` (integração via nó fake que registra).
"""

from __future__ import annotations

from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from packages.agents import run_pipeline
from packages.observability.cost import (
    DEFAULT_PRICE,
    USAGE_RECORDER,
    TokenUsage,
    capture_usage,
    estimate_cost,
    extract_usage,
    record_usage,
)

_SUPER = "nvidia/llama-3.3-nemotron-super-49b-v1"
_NANO = "nvidia/llama-3.1-nemotron-nano-8b-v1"


def _result(usage_metadata: dict | None, *, model: str = _SUPER, llm_output: dict | None = None):
    if usage_metadata is not None:
        # AIMessage exige total_tokens no usage_metadata; deriva se o teste não passar.
        usage_metadata = {
            "total_tokens": usage_metadata.get("input_tokens", 0)
            + usage_metadata.get("output_tokens", 0),
            **usage_metadata,
        }
    msg = AIMessage(
        content="ok",
        usage_metadata=usage_metadata,  # type: ignore[arg-type]
        response_metadata={"model_name": model},
    )
    return LLMResult(generations=[[ChatGeneration(message=msg)]], llm_output=llm_output)


# --- estimate_cost ------------------------------------------------------------


def test_estimate_cost_uses_table_by_substring() -> None:
    # super é mais caro que nano p/ o mesmo nº de tokens (saída de raciocínio).
    assert estimate_cost(_SUPER, 1_000_000, 1_000_000) > estimate_cost(_NANO, 1_000_000, 1_000_000)


def test_estimate_cost_unknown_model_falls_back_to_default() -> None:
    cost = estimate_cost("modelo-desconhecido", 1_000_000, 0)
    assert cost == round(DEFAULT_PRICE.input_per_1m, 6)


def test_estimate_cost_embeddings_have_no_output_price() -> None:
    # nv-embedqa: saída custa 0 → só a entrada conta.
    assert estimate_cost("nvidia/llama-3.2-nv-embedqa-1b-v2", 0, 1_000_000) == 0.0


# --- TokenUsage ---------------------------------------------------------------


def test_token_usage_merge_sums_fields() -> None:
    a = TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15, calls=1, cost_usd=0.001)
    b = TokenUsage(input_tokens=20, output_tokens=10, total_tokens=30, calls=1, cost_usd=0.002)
    merged = a.merge(b)
    assert (merged.input_tokens, merged.output_tokens, merged.total_tokens) == (30, 15, 45)
    assert merged.calls == 2
    assert merged.cost_usd == 0.003


def test_token_usage_for_call_sets_total_and_cost() -> None:
    usage = TokenUsage.for_call(model=_NANO, input_tokens=100, output_tokens=50)
    assert usage.calls == 1
    assert usage.total_tokens == 150
    assert usage.cost_usd == estimate_cost(_NANO, 100, 50)


# --- extract_usage ------------------------------------------------------------


def test_extract_usage_from_langchain_metadata() -> None:
    result = _result({"input_tokens": 100, "output_tokens": 40, "total_tokens": 140})
    usage = extract_usage(result)
    assert (usage.input_tokens, usage.output_tokens, usage.calls) == (100, 40, 1)
    assert usage.cost_usd == estimate_cost(_SUPER, 100, 40)


def test_extract_usage_from_openai_like_llm_output() -> None:
    token_usage = {"prompt_tokens": 30, "completion_tokens": 12}
    usage = extract_usage(_result(None, llm_output={"token_usage": token_usage}))
    assert (usage.input_tokens, usage.output_tokens) == (30, 12)


def test_extract_usage_counts_call_even_without_tokens() -> None:
    usage = extract_usage(_result(None))
    assert usage.calls == 1
    assert usage.total_tokens == 0


# --- capture / record ---------------------------------------------------------


def test_record_usage_is_noop_outside_scope() -> None:
    # fora de um capture_usage não levanta nem acumula em lugar nenhum.
    record_usage(TokenUsage.for_call(model=_NANO, input_tokens=1, output_tokens=1))


def test_capture_usage_accumulates_in_scope() -> None:
    with capture_usage() as usage:
        record_usage(TokenUsage.for_call(model=_NANO, input_tokens=100, output_tokens=50))
        record_usage(TokenUsage.for_call(model=_SUPER, input_tokens=200, output_tokens=80))
        total = usage.total()
    assert total.calls == 2
    assert total.total_tokens == 430
    assert total.cost_usd > 0


def test_capture_usage_resets_between_scopes() -> None:
    with capture_usage() as first:
        record_usage(TokenUsage.for_call(model=_NANO, input_tokens=10, output_tokens=5))
        assert first.total().calls == 1
    with capture_usage() as second:
        assert second.total().calls == 0  # escopo novo começa zerado (sem leak)


def test_usage_recorder_measures_on_llm_end() -> None:
    with capture_usage() as usage:
        USAGE_RECORDER.on_llm_end(_result({"input_tokens": 70, "output_tokens": 30}))
        total = usage.total()
    assert total.calls == 1
    assert total.input_tokens == 70


# --- integração com run_pipeline ----------------------------------------------


def test_run_pipeline_offline_has_no_usage() -> None:
    # espinha offline (sem LLM) → nenhum uso medido, trace fica intacto (M2/DoD).
    out = run_pipeline("Acme AI", run_id="run-cost-0")
    assert "usage" not in out.trace


def test_run_pipeline_stamps_usage_when_llm_called(monkeypatch) -> None:
    # nó fake registrando uso no escopo (simula uma chamada LLM) → rollup em trace["usage"].
    from packages.agents import nodes

    def fake_classifier(state):  # noqa: ANN001, ANN202
        record_usage(TokenUsage.for_call(model=_SUPER, input_tokens=300, output_tokens=120))
        return {}

    monkeypatch.setitem(nodes.NODES, "classifier", fake_classifier)
    out = run_pipeline("Acme AI", run_id="run-cost-1")
    assert out.trace["usage"]["calls"] == 1
    assert out.trace["usage"]["total_tokens"] == 420
    assert out.trace["usage"]["cost_usd"] > 0
