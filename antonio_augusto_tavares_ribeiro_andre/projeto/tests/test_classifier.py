"""Testes do nó classifier (F2.6).

Tudo offline/determinista (o caminho LLM é opt-in via `classifier_use_llm` + chave, ou
injetando um adapter `classify=`). Exercita:
- `heuristic_score` (v1): classe pelo *papel* da IA (§5.1) + 4 pilares 0–25 pela RUBRICA
  (F0.11), com evidência colada ao sub-score e a trava §0 (>6 exige evidência);
- a faixa "Forte/Defensável" (19–25) só com corroboração (sinal forte + ≥2 fontes), e o teto
  "Estabelecido" (18) sem ela;
- a região "wrapper" emergindo (AI-native + P3 baixo quando só há API externa);
- `parse_score`: JSON do Super → `AIMIScore` ancorado na proveniência do perfil, rebaixando
  sub-score sem evidência; `classify_with_llm` degradando p/ None sem alucinar;
- `make_aimi`: heurística por default, Super quando ligado, fallback à heurística;
- o nó: no-op sem perfil (espinha verde, M2), `aimi` com perfil, e `classify=` injetado.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

import packages.agents.classifier as cl
from packages.agents.classifier import (
    classifier,
    classify_with_llm,
    heuristic_score,
    make_aimi,
    parse_score,
)
from packages.schemas import (
    AIMIBand,
    AIMIScore,
    Claim,
    Classification,
    Customer,
    Evidence,
    Funding,
    GraphState,
    Product,
    StartupProfile,
    Technology,
)

_FETCHED = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _offline_classifier_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """Crava este módulo offline: um `.env` de dev com `CLASSIFIER_USE_LLM=true` faria
    `make_aimi`/`classifier` (sem `classify=` injetado) chamar o Super **ao vivo** — passaria
    na CI (sem flags) e falharia *flaky* local (a LLM é não-determinística; mede-se 4/6 rodadas
    divergindo da heurística). Mesmo padrão da guarda de `test_ragas` p/ `EMBEDDINGS_USE_NV`.
    Os testes que querem o LLM ligam o flag (`use_llm=True`) ou injetam o adapter; ambos são
    function-scoped e sobrepõem este default depois daqui."""
    monkeypatch.setattr(cl, "get_settings", lambda: _FakeSettings(use_llm=False))


def _ev(url: str = "https://acme.ai", snippet: str = "trecho de suporte") -> Evidence:
    return Evidence(url=url, snippet=snippet, fetched_at=_FETCHED, content_hash="h-acme")


def _claim(value: str, evidence: list[Evidence] | None = None) -> Claim[str]:
    return Claim[str](value=value, evidence=evidence if evidence is not None else [_ev()])


def _ai_native_own_stack() -> StartupProfile:
    """AI-native com stack própria: agentes + serving próprio + fine-tuning + tração."""
    return StartupProfile(
        nome="Acme AI",
        descricao=_claim(
            "Plataforma de agentes de IA que automatiza o workflow de ponta a ponta para fintechs."
        ),
        setor=_claim("Fintech"),
        produtos=[
            Product(nome="Copilot", descricao="agente que integra sistemas", evidence=[_ev()])
        ],
        tecnologias=[
            Technology(
                nome="NIM",
                categoria="serving",
                uso="inferência própria com fine-tuning",
                evidence=[_ev()],
            )
        ],
        clientes=[
            Customer(nome="BancoX", enterprise=True, evidence=[_ev()]),
            Customer(nome="BancoY", enterprise=True, evidence=[_ev()]),
            Customer(nome="BancoZ", evidence=[_ev()]),
        ],
        funding=Funding(total_raised_usd=5_000_000, investors=["Fundo Z"], evidence=[_ev()]),
        source_urls=["https://acme.ai"],
    )


def _ai_native_corroborated() -> StartupProfile:
    """Stack própria forte **com evidência multi-fonte** → habilita a faixa Forte (v1).

    Sinais fortes de P3 (serving próprio, fine-tuning, Triton/TensorRT) ancorados em ≥2 URLs
    independentes — a corroboração que a v1 exige para cruzar de "Estabelecido" para "Forte".
    """
    return StartupProfile(
        nome="DeepStack AI",
        descricao=_claim(
            "Plataforma que serve modelos próprios com fine-tuning e Triton em GPU.",
            evidence=[_ev(url="https://deepstack.ai")],
        ),
        tecnologias=[
            Technology(
                nome="Triton + TensorRT-LLM",
                categoria="serving",
                uso="serving próprio com fine-tuning e quantização",
                evidence=[
                    _ev(url="https://deepstack.ai/tech"),
                    _ev(url="https://blog.deepstack.ai/infra"),
                ],
            )
        ],
        source_urls=["https://deepstack.ai"],
    )


def _wrapper() -> StartupProfile:
    """AI-native pelo papel da IA, mas 100% API externa → região 'wrapper' (P3 baixo)."""
    return StartupProfile(
        nome="ChatCo",
        descricao=_claim(
            "Wrapper de IA: um chat que usa a API da OpenAI para responder perguntas."
        ),
        produtos=[Product(nome="ChatBot", descricao="agente de chat", evidence=[_ev()])],
        tecnologias=[
            Technology(
                nome="OpenAI API",
                categoria="LLM provider",
                uso="chamadas de api",
                evidence=[_ev()],
            )
        ],
        source_urls=["https://acme.ai"],
    )


def _non_ai() -> StartupProfile:
    return StartupProfile(
        nome="Loja X",
        descricao=_claim("Loja de roupas online com catálogo e checkout."),
        produtos=[Product(nome="E-commerce", descricao="catálogo de produtos", evidence=[_ev()])],
        source_urls=["https://acme.ai"],
    )


# ------------------------------------------------------------------- heuristic_score (v1)


def test_heuristic_ai_native_with_own_stack() -> None:
    aimi = heuristic_score(_ai_native_own_stack())
    assert isinstance(aimi, AIMIScore)
    assert aimi.classificacao is Classification.AI_NATIVE
    assert aimi.heuristic_version == "v1"
    # stack própria (serving/fine-tuning) → P3 sobe da faixa de wrapper.
    assert aimi.technical_optimization.score >= 13
    assert aimi.technical_optimization.evidencia  # sub-score alto vem com evidência
    # total = soma dos pilares (fonte única do schema).
    assert aimi.total == sum(p.score for p in aimi.pillars)


def test_heuristic_wrapper_is_ai_native_but_p3_low() -> None:
    aimi = heuristic_score(_wrapper())
    # wrapper NÃO é classe: continua AI-native, mas com P3 baixo (gatilho de graduação).
    assert aimi.classificacao is Classification.AI_NATIVE
    assert aimi.technical_optimization.score <= 6
    assert "graduação" in aimi.technical_optimization.justificativa


def test_heuristic_non_ai() -> None:
    aimi = heuristic_score(_non_ai())
    assert aimi.classificacao is Classification.NON_AI


def test_heuristic_v1_caps_at_established_without_corroboration() -> None:
    # Stack própria forte, mas evidência de uma única fonte (acme.ai): sem corroboração, o
    # sub-score não cruza para "Forte" — fica no teto "Estabelecido" (18).
    aimi = heuristic_score(_ai_native_own_stack())
    p3 = aimi.technical_optimization
    assert p3.score <= cl.ESTABLISHED_CEILING
    assert p3.band is AIMIBand.ESTABELECIDO


def test_heuristic_v1_reaches_forte_with_corroboration() -> None:
    # Sinais fortes de stack própria + ≥2 fontes independentes → faixa "Forte/Defensável" (19–25).
    aimi = heuristic_score(_ai_native_corroborated())
    p3 = aimi.technical_optimization
    assert p3.score >= cl.STRONG_BAND_FLOOR
    assert p3.band is AIMIBand.FORTE
    assert cl._n_sources(p3.evidencia) >= cl.MIN_SOURCES_FOR_STRONG  # corroboração real


def test_heuristic_evidence_gate_caps_score_without_evidence() -> None:
    # sinais de workflow fortes, mas SEM evidência citável → trava em ≤6 (RUBRICA §0)
    # e, sem confiança, a classe não chega a AI-native (cai em AI-enabled).
    prof = StartupProfile(
        nome="X",
        descricao=Claim[str](
            value="agentes de IA que automatizam o workflow de ponta a ponta", evidence=[]
        ),
    )
    aimi = heuristic_score(prof)
    assert aimi.workflow_depth.score <= 6
    assert aimi.workflow_depth.evidencia == []
    assert aimi.classificacao is Classification.AI_ENABLED


def test_heuristic_distribution_uses_enterprise_and_funding() -> None:
    aimi = heuristic_score(_ai_native_own_stack())
    p4 = aimi.distribution_moat
    assert p4.score > 6  # enterprise + captação empurram o pilar
    assert p4.evidencia
    assert "Tração" in p4.justificativa


# ---------------------------------------------------------- explicabilidade do sub-score (F6.2)


def test_every_subscore_is_explainable() -> None:
    # Cada pilar carrega o cálculo ("base ... = N") na justificativa — o número não é caixa-preta.
    aimi = heuristic_score(_ai_native_own_stack())
    for p in aimi.pillars:
        assert "Cálculo:" in p.justificativa
        # o total citado no breakdown bate com o score real do pilar.
        assert f"= {p.score}" in p.justificativa


def test_breakdown_explains_established_ceiling_without_corroboration() -> None:
    # Stack própria forte de fonte única: o cálculo deve dizer por que parou em "Estabelecido".
    p3 = heuristic_score(_ai_native_own_stack()).technical_optimization
    assert "teto Estabelecido" in p3.justificativa
    assert "sem corroboração" in p3.justificativa


def test_breakdown_explains_forte_band_with_corroboration() -> None:
    # Faixa Forte liberada → o cálculo cita a corroboração que a habilitou.
    p3 = heuristic_score(_ai_native_corroborated()).technical_optimization
    assert "faixa Forte liberada" in p3.justificativa
    assert "corroboração" in p3.justificativa


def test_breakdown_explains_graduation_trigger_for_api_wrapper() -> None:
    # Wrapper 100% API externa: justificativa cita o gatilho de graduação + traz o cálculo.
    p3 = heuristic_score(_wrapper()).technical_optimization
    assert "alvo de graduação" in p3.justificativa
    assert "Cálculo:" in p3.justificativa
    assert p3.score <= 6


# ------------------------------------------------------------------------- parse_score (LLM)


def _llm_json(*, classe: str = "ai_native", score: int = 15, url: str = "https://acme.ai") -> str:
    pillar = {
        "score": score,
        "justificativa": "tem sinais claros",
        "evidence": [{"url": url, "snippet": "trecho"}],
    }
    return json.dumps(
        {
            "classificacao": classe,
            "confidence": 0.8,
            "data_moat": pillar,
            "workflow_depth": pillar,
            "technical_optimization": pillar,
            "distribution_moat": pillar,
        }
    )


def test_parse_score_grounds_evidence_in_profile() -> None:
    profile = _ai_native_own_stack()
    aimi = parse_score(_llm_json(), profile=profile)
    assert aimi.classificacao is Classification.AI_NATIVE
    assert aimi.confidence == 0.8
    assert aimi.data_moat.score == 15
    # evidência reusa a proveniência real do perfil (fetched_at do doc, não 'agora').
    assert aimi.data_moat.evidencia[0].fetched_at == _FETCHED


def test_parse_score_caps_score_without_cited_evidence() -> None:
    # modelo afirma 20 mas não cita evidência → rebaixado a 6 (RUBRICA §0), sem derrubar.
    raw = json.dumps(
        {
            "classificacao": "AI-native",  # alias kebab também é aceito
            "data_moat": {"score": 20, "justificativa": "alto", "evidence": []},
            "workflow_depth": {"score": 5, "justificativa": "baixo"},
            "technical_optimization": {"score": 5, "justificativa": "baixo"},
            "distribution_moat": {"score": 5, "justificativa": "baixo"},
        }
    )
    aimi = parse_score(raw, profile=_ai_native_own_stack())
    assert aimi.classificacao is Classification.AI_NATIVE
    assert aimi.data_moat.score == 6
    assert aimi.data_moat.evidencia == []


def test_parse_score_new_url_gets_policy_not_doc_provenance() -> None:
    raw = json.dumps(
        {
            "classificacao": "ai_enabled",
            "data_moat": {
                "score": 10,
                "justificativa": "ok",
                "evidence": [{"url": "https://braziljournal.com/x", "snippet": "cobertura"}],
            },
            "workflow_depth": {"score": 3, "justificativa": "x"},
            "technical_optimization": {"score": 3, "justificativa": "x"},
            "distribution_moat": {"score": 3, "justificativa": "x"},
        }
    )
    aimi = parse_score(raw, profile=_ai_native_own_stack())
    ev = aimi.data_moat.evidencia[0]
    assert ev.content_hash is None  # url nova (não estava no perfil)
    assert ev.source_policy  # política de ToS carimbada (F1.15)


# ------------------------------------------------------------------------ classify_with_llm


def test_classify_with_llm_injected_adapter() -> None:
    aimi = classify_with_llm(_ai_native_own_stack(), classify=lambda p: _llm_json())
    assert aimi is not None
    assert aimi.classificacao is Classification.AI_NATIVE


def test_classify_with_llm_returns_none_on_bad_json() -> None:
    assert classify_with_llm(_ai_native_own_stack(), classify=lambda p: "sem json") is None


def test_classify_with_llm_returns_none_when_adapter_raises() -> None:
    def boom(p: StartupProfile) -> str:
        raise RuntimeError("modelo fora do ar")

    assert classify_with_llm(_ai_native_own_stack(), classify=boom) is None


# ------------------------------------------------------------------------------- make_aimi


def test_make_aimi_default_is_heuristic() -> None:
    profile = _wrapper()
    aimi = make_aimi(profile)
    assert aimi.heuristic_version == "v1"
    assert aimi.classificacao is heuristic_score(profile).classificacao


def test_make_aimi_uses_injected_classify() -> None:
    # adapter força non_ai (diferente da heurística AI-native) → prova que o LLM foi usado.
    aimi = make_aimi(_wrapper(), classify=lambda p: _llm_json(classe="non_ai"))
    assert aimi.classificacao is Classification.NON_AI


def test_make_aimi_falls_back_to_heuristic_on_llm_failure() -> None:
    profile = _wrapper()
    aimi = make_aimi(profile, classify=lambda p: "lixo sem json")
    assert aimi.classificacao is heuristic_score(profile).classificacao


def test_make_aimi_uses_llm_when_flag_on(monkeypatch) -> None:
    monkeypatch.setattr(cl, "get_settings", lambda: _FakeSettings(use_llm=True))
    monkeypatch.setattr(cl, "_default_classify", lambda p, run_id=None: _llm_json(classe="non_ai"))
    aimi = make_aimi(_wrapper())
    assert aimi.classificacao is Classification.NON_AI


# ------------------------------------------------------------------------------- nó


def test_node_no_profile_is_noop() -> None:
    state = GraphState(run_id="r1", query="Acme")
    assert classifier(state) == {}


def test_node_with_profile_returns_aimi() -> None:
    state = GraphState(run_id="r1", query="Acme AI", profile=_ai_native_own_stack())
    update = classifier(state)
    assert isinstance(update["aimi"], AIMIScore)
    assert update["aimi"].classificacao is Classification.AI_NATIVE


def test_node_with_injected_classify() -> None:
    state = GraphState(run_id="r1", query="Acme AI", profile=_wrapper())
    update = classifier(state, classify=lambda p: _llm_json(classe="non_ai"))
    assert update["aimi"].classificacao is Classification.NON_AI


class _FakeSettings:
    def __init__(self, *, use_llm: bool) -> None:
        self.classifier_use_llm = use_llm
