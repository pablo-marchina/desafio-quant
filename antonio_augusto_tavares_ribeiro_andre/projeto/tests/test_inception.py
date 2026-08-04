"""Testes do Inception Priority (F6.13): fila de outreach 0–100 = potencial × upside × classe.

Exercita:
- a **função pura** `inception_priority` (deriva só do AIMI, sem rede/GPU): limites [0,100],
  a ordenação multiplicativa (upside por P3 baixo, potencial por P1/P2, peso da classe) e os
  **fatores** explicáveis (ALINHAMENTO §9);
- o **wiring** no classifier — `heuristic_score` e `parse_score` carimbam o campo do `AIMIScore`;
- a exibição no **briefing** (F4.4): campo `inception_priority` + a linha no Markdown.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from packages.agents.briefing import build_briefing, render_markdown
from packages.agents.classifier import heuristic_score, parse_score
from packages.agents.inception import inception_priority
from packages.schemas import (
    AIMIPillar,
    AIMIScore,
    Claim,
    Classification,
    Evidence,
    PillarScore,
    StartupProfile,
    Technology,
)

_FETCHED = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)


def _ev() -> Evidence:
    return Evidence(url="https://acme.ai", snippet="trecho", fetched_at=_FETCHED)


def _pillar(pilar: AIMIPillar, score: int) -> PillarScore:
    # RUBRICA §0: sub-score > 6 exige evidência citável; ≤6 dispensa.
    ev = [_ev()] if score > 6 else []
    return PillarScore(pilar=pilar, score=score, justificativa="j", evidencia=ev)


def _aimi(
    p1: int, p2: int, p3: int, p4: int, classe: Classification = Classification.AI_NATIVE
) -> AIMIScore:
    return AIMIScore(
        data_moat=_pillar(AIMIPillar.DATA_MOAT, p1),
        workflow_depth=_pillar(AIMIPillar.WORKFLOW_DEPTH, p2),
        technical_optimization=_pillar(AIMIPillar.TECHNICAL_OPTIMIZATION, p3),
        distribution_moat=_pillar(AIMIPillar.DISTRIBUTION_MOAT, p4),
        classificacao=classe,
    )


def _profile() -> StartupProfile:
    """AI-native (IA no núcleo + workflow) 100% API externa → P3 baixo, alvo de graduação."""
    return StartupProfile(
        nome="Acme",
        descricao=Claim[str](
            value="agentes de IA que automatizam o workflow de ponta a ponta",
            evidence=[_ev()],
        ),
        tecnologias=[
            Technology(nome="OpenAI API", categoria="LLM", uso="chamadas de api", evidence=[_ev()])
        ],
        source_urls=["https://acme.ai"],
    )


# ------------------------------------------------------------------ função pura


def test_priority_within_bounds() -> None:
    for vals in ((25, 25, 0, 25), (0, 0, 25, 0), (20, 20, 5, 10), (12, 8, 12, 6)):
        score, _ = inception_priority(_aimi(*vals))
        assert 0 <= score <= 100


def test_graduation_target_beats_already_optimized() -> None:
    # Mesmo potencial alto (P1/P2); decide o upside — P3 baixo (a graduar) > P3 alto (pronto).
    target = inception_priority(_aimi(20, 20, 4, 10))[0]
    optimized = inception_priority(_aimi(20, 20, 22, 10))[0]
    assert target > optimized


def test_graduation_target_beats_thin_wrapper() -> None:
    # Mesmo upside (P3 baixo); o que decide é o potencial — moat/workflow reais > wrapper sem moat.
    target = inception_priority(_aimi(20, 20, 4, 10))[0]
    wrapper = inception_priority(_aimi(3, 5, 4, 3))[0]
    assert target > wrapper


def test_class_weight_orders_native_enabled_nonai() -> None:
    # Mesmos pilares; só a classe muda — AI-native no topo, non-AI fora do alvo (0).
    pillars = (20, 20, 4, 10)
    native = inception_priority(_aimi(*pillars, Classification.AI_NATIVE))[0]
    enabled = inception_priority(_aimi(*pillars, Classification.AI_ENABLED))[0]
    nonai = inception_priority(_aimi(*pillars, Classification.NON_AI))[0]
    assert native > enabled > nonai
    assert nonai == 0


def test_factors_are_explainable() -> None:
    # O score nunca é caixa-preta: os fatores citam potencial/upside, os pilares e o total.
    score, fatores = inception_priority(_aimi(20, 18, 4, 10))
    assert "potencial AI-native" in fatores
    assert "upside" in fatores
    assert "Data Moat 20/25" in fatores
    assert "Workflow Depth 18/25" in fatores
    assert f"= {score}/100" in fatores


# ------------------------------------------------------------------ wiring no classifier


def test_heuristic_score_fills_inception_priority() -> None:
    aimi = heuristic_score(_profile())
    assert aimi.inception_priority is not None
    # o campo carimbado bate com a função pura sobre o mesmo AIMI.
    assert aimi.inception_priority == inception_priority(aimi)[0]
    assert 0 <= aimi.inception_priority <= 100


def test_parse_score_fills_inception_priority() -> None:
    pillar = {
        "score": 15,
        "justificativa": "tem sinais",
        "evidence": [{"url": "https://acme.ai", "snippet": "trecho"}],
    }
    raw = json.dumps(
        {
            "classificacao": "ai_native",
            "confidence": 0.8,
            "data_moat": pillar,
            "workflow_depth": pillar,
            "technical_optimization": pillar,
            "distribution_moat": pillar,
        }
    )
    aimi = parse_score(raw, profile=_profile())
    assert aimi.inception_priority is not None
    assert aimi.inception_priority == inception_priority(aimi)[0]


# ------------------------------------------------------------------ exibição no briefing


def test_briefing_surfaces_inception_priority() -> None:
    aimi = heuristic_score(_profile())
    briefing = build_briefing(aimi, None, [], empresa="Acme")
    assert briefing.inception_priority == inception_priority(aimi)[0]
    md = render_markdown(briefing)
    assert "Inception Priority" in md
    assert f"{briefing.inception_priority}/100" in md
