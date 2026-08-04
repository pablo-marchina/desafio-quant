"""Testes do nó evidence_validator (F2.7).

Tudo offline/determinista. Exercita:
- `evidence_sources`/`is_sufficient`: contagem de fontes **independentes** (host distinto,
  `www.` normalizado), unindo `all_evidence` + `source_urls`;
- o nó roteando por `Command`: sem perfil → segue; ≥ N hosts → segue; insuficiente com
  orçamento → retry ao scraper (incrementa `retry_count`, marca RUNNING); insuficiente e
  esgotado → terminal de baixa confiança (F2.12: salta ao briefing, marca INSUFFICIENT_DATA
  + nota rastreável, sem alucinar nem loop);
- F2.13: `is_confident_non_ai` + no ramo corroborado, classe non-AI confiante → terminal "fora
  de escopo" (OUT_OF_SCOPE), disjunto de "dados insuficientes" (non-AI sem corroboração → F2.12);
- o **loop de retry termina** em exatamente `max_retries` re-coletas (DoD F2 "retry funciona");
- coerência das constantes de roteamento com a espinha (`graph.PIPELINE`).
"""

from __future__ import annotations

from datetime import UTC, datetime

from packages.agents import evidence_sources, is_confident_non_ai, is_sufficient
from packages.agents.evidence_validator import (
    CONTINUE_TARGET,
    MIN_SOURCES,
    RETRY_TARGET,
    TERMINAL_TARGET,
    evidence_validator,
)
from packages.agents.graph import PIPELINE
from packages.schemas import (
    AIMIPillar,
    AIMIScore,
    Claim,
    Classification,
    Evidence,
    GraphState,
    PillarScore,
    RawDocument,
    RunStatus,
    StartupProfile,
)

_FETCHED = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)


def _ev(url: str) -> Evidence:
    return Evidence(url=url, snippet="trecho", fetched_at=_FETCHED, content_hash="h")


def _profile(*ev_urls: str, source_urls: list[str] | None = None) -> StartupProfile:
    """Perfil cuja proveniência são as URLs dadas (evidência da descrição + fontes agregadas)."""
    return StartupProfile(
        nome="X",
        descricao=Claim[str](value="o que a empresa faz", evidence=[_ev(u) for u in ev_urls]),
        source_urls=source_urls or [],
    )


def _aimi(classe: Classification, confidence: float | None) -> AIMIScore:
    """AIMIScore mínimo (pilares ausentes ≤6, sem evidência) só p/ exercitar classe+confiança."""

    def pilar(p: AIMIPillar) -> PillarScore:
        return PillarScore(pilar=p, score=3, justificativa="ausente")

    return AIMIScore(
        data_moat=pilar(AIMIPillar.DATA_MOAT),
        workflow_depth=pilar(AIMIPillar.WORKFLOW_DEPTH),
        technical_optimization=pilar(AIMIPillar.TECHNICAL_OPTIMIZATION),
        distribution_moat=pilar(AIMIPillar.DISTRIBUTION_MOAT),
        classificacao=classe,
        confidence=confidence,
    )


def _state(profile: StartupProfile | None, **kw) -> GraphState:
    return GraphState(run_id="r1", query="X", profile=profile, **kw)


# --------------------------------------------------------- contagem de fontes (regra de N)


def test_evidence_sources_counts_distinct_hosts_normalizing_www() -> None:
    # mesmo host por caminhos diferentes + www → UMA fonte (auto-relato, não corrobora).
    prof = _profile("https://acme.ai/sobre", "https://www.acme.ai/produtos")
    assert evidence_sources(prof) == {"acme.ai"}
    assert not is_sufficient(prof)


def test_evidence_sources_unites_evidence_and_source_urls() -> None:
    # corroboração real: descrição citada em acme.ai + fonte agregada de outro veículo.
    prof = _profile("https://acme.ai/sobre", source_urls=["https://braziljournal.com/x"])
    assert evidence_sources(prof) == {"acme.ai", "braziljournal.com"}
    assert is_sufficient(prof)


def test_is_sufficient_respects_min_sources_threshold() -> None:
    prof = _profile("https://a.com", "https://b.com", "https://c.com")
    assert is_sufficient(prof)  # 3 ≥ 2 (default)
    assert not is_sufficient(prof, min_sources=4)


# ------------------------------------------------------------------------ roteamento do nó


def test_node_no_profile_continues_without_retry() -> None:
    # espinha offline (sem extração): nada a corroborar → segue limpo, sem retry/erro.
    cmd = evidence_validator(_state(None))
    assert cmd.goto == CONTINUE_TARGET
    assert cmd.update is None


def test_node_no_profile_after_collection_routes_to_insufficient_data() -> None:
    # Extração falhou (coletou docs mas não produziu perfil, F2.5): NÃO pode seguir como a espinha
    # offline — isso concluiria o run COMPLETED sem briefing (o /briefings 404, o front oferece um
    # PDF inexistente). Salta ao briefing terminal F2.12, marcando INSUFFICIENT_DATA + nota.
    doc = RawDocument(url="https://rivio.ai", content="conteúdo", fetched_at=_FETCHED)
    cmd = evidence_validator(_state(None, raw_docs=[doc]))
    assert cmd.goto == TERMINAL_TARGET
    assert cmd.update["status"] is RunStatus.INSUFFICIENT_DATA
    assert any("não produziu um perfil" in e for e in cmd.update["errors"])


def test_node_no_profile_with_errors_routes_to_insufficient_data() -> None:
    # Coleta rodou e registrou erro (ex.: scraper/extractor), mas sem perfil → mesmo terminal F2.12
    # (em vez de fingir conclusão sem briefing). A nota da extração é preservada e acumulada.
    cmd = evidence_validator(_state(None, errors=["extractor: extração não produziu um perfil"]))
    assert cmd.goto == TERMINAL_TARGET
    assert cmd.update["status"] is RunStatus.INSUFFICIENT_DATA
    assert cmd.update["errors"][0] == "extractor: extração não produziu um perfil"  # preserva


def test_node_sufficient_continues() -> None:
    cmd = evidence_validator(_state(_profile("https://a.com", "https://b.com")))
    assert cmd.goto == CONTINUE_TARGET
    assert cmd.update is None


# ---------------------------------- F2.13: non-AI de alta confiança → fora de escopo


def test_is_confident_non_ai_predicate() -> None:
    assert is_confident_non_ai(None) is False  # sem diagnóstico
    assert is_confident_non_ai(_aimi(Classification.NON_AI, 0.8)) is True
    assert is_confident_non_ai(_aimi(Classification.NON_AI, 0.49)) is False  # abaixo do piso
    assert is_confident_non_ai(_aimi(Classification.NON_AI, None)) is False  # sem confiança
    assert is_confident_non_ai(_aimi(Classification.AI_NATIVE, 0.99)) is False  # não é non-AI


def test_node_confident_non_ai_routes_to_out_of_scope() -> None:
    # Corroborado (2 hosts) + classe non-AI cravada com confiança → terminal "fora de escopo":
    # salta ao briefing marcando OUT_OF_SCOPE, sem seguir ao RAG nem nota de erro (legítimo).
    state = _state(
        _profile("https://a.com", "https://b.com"),
        aimi=_aimi(Classification.NON_AI, 0.8),
    )
    cmd = evidence_validator(state)
    assert cmd.goto == TERMINAL_TARGET
    assert cmd.update == {"status": RunStatus.OUT_OF_SCOPE}
    assert "errors" not in cmd.update  # não é falha → não polui errors


def test_node_non_ai_low_confidence_continues_normally() -> None:
    # Corroborado, mas a classe non-AI não é firme (confiança < piso) → segue o caminho normal.
    state = _state(
        _profile("https://a.com", "https://b.com"),
        aimi=_aimi(Classification.NON_AI, 0.3),
    )
    cmd = evidence_validator(state)
    assert cmd.goto == CONTINUE_TARGET
    assert cmd.update is None


def test_confident_non_ai_without_corroboration_falls_to_insufficient_data() -> None:
    # Disjunção dos terminais: non-AI confiante mas com 1 fonte (< piso) NÃO é "fora de escopo" —
    # sem corroboração cai em "dados insuficientes" (F2.12), não se descarta a empresa.
    state = _state(
        _profile("https://a.com"),
        aimi=_aimi(Classification.NON_AI, 0.9),
        max_retries=0,
    )
    cmd = evidence_validator(state)
    assert cmd.goto == TERMINAL_TARGET
    assert cmd.update["status"] is RunStatus.INSUFFICIENT_DATA  # não OUT_OF_SCOPE


def test_node_insufficient_with_budget_retries_to_scraper() -> None:
    cmd = evidence_validator(_state(_profile("https://a.com"), retry_count=0, max_retries=2))
    assert cmd.goto == RETRY_TARGET
    assert cmd.update == {"retry_count": 1, "status": RunStatus.RUNNING}


def test_node_insufficient_exhausted_routes_to_terminal() -> None:
    # F2.12: retry esgotado e ainda insuficiente → salta ao briefing terminal, marca
    # INSUFFICIENT_DATA e deixa a nota rastreável (não segue ao RAG nem alucina).
    cmd = evidence_validator(_state(_profile("https://a.com"), retry_count=2, max_retries=2))
    assert cmd.goto == TERMINAL_TARGET
    assert cmd.update["status"] is RunStatus.INSUFFICIENT_DATA
    assert len(cmd.update["errors"]) == 1
    note = cmd.update["errors"][0]
    assert "evidência insuficiente" in note
    assert "1 fonte" in note  # contou 1 host independente


# --------------------------------------------------- o loop termina (DoD: retry funciona)


def test_retry_loop_terminates_after_max_retries() -> None:
    # Pior caso: o re-scrape nunca acha fonte nova (perfil de 1 host fica fixo). O loop deve
    # bater no scraper exatamente max_retries vezes e então cair no terminal — sem laço infinito.
    max_retries = 2
    state = _state(_profile("https://a.com"), max_retries=max_retries)
    routes: list[str] = []
    for _ in range(max_retries + 5):  # cota de segurança contra loop infinito no teste
        cmd = evidence_validator(state)
        routes.append(cmd.goto)
        state = state.model_copy(update=cmd.update or {})  # imita o overwrite do LangGraph
        if cmd.goto == TERMINAL_TARGET:
            break

    assert routes == [RETRY_TARGET, RETRY_TARGET, TERMINAL_TARGET]
    assert state.retry_count == max_retries  # contador limpo: nunca passa do orçamento
    assert state.status is RunStatus.INSUFFICIENT_DATA  # F2.12: terminal de baixa confiança
    assert len(state.errors) == 1  # nota só no passo terminal


def test_retry_disabled_when_max_retries_zero() -> None:
    # max_retries=0 ⇒ sem orçamento: insuficiente cai direto no terminal F2.12 (não re-coleta).
    cmd = evidence_validator(_state(_profile("https://a.com"), max_retries=0))
    assert cmd.goto == TERMINAL_TARGET
    assert cmd.update["status"] is RunStatus.INSUFFICIENT_DATA
    assert "errors" in cmd.update


# -------------------------------------------------------- coerência com a espinha (graph.py)


def test_routing_targets_match_pipeline() -> None:
    assert RETRY_TARGET in PIPELINE
    assert CONTINUE_TARGET in PIPELINE
    assert TERMINAL_TARGET in PIPELINE
    # o caminho normal é o nó imediatamente seguinte na espinha; o retry volta ao scraper;
    # o terminal F2.12 salta ao último nó (briefing), pulando RAG/recomendação/benchmark.
    i = PIPELINE.index("evidence_validator")
    assert PIPELINE[i + 1] == CONTINUE_TARGET
    assert PIPELINE.index(RETRY_TARGET) < i
    assert TERMINAL_TARGET == PIPELINE[-1]
    assert MIN_SOURCES >= 2
