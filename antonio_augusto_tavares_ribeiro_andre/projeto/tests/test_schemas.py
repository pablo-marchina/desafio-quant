"""Testes mínimos dos contratos Pydantic (F0.5 — DoD).

Cobre os invariantes que o resto do plano depende:
- import público (`from packages.schemas import ...`);
- regra de evidência do AIMI (RUBRICA §0: score > 6 exige evidência);
- AIMI total = soma dos pilares + derivação de faixa;
- recomendação exige evidência dos **dois lados** (Guardrails F4.5);
- proveniência por campo no perfil; round-trip JSON do estado.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from packages.schemas import (
    AIMIBand,
    AIMIPillar,
    AIMIScore,
    Briefing,
    Claim,
    Classification,
    Complexity,
    Evidence,
    GraphState,
    PillarScore,
    Priority,
    Recommendation,
    StartupProfile,
    Technology,
    band_for,
)


def _ev(snippet: str = "trecho") -> Evidence:
    return Evidence(
        url="https://exemplo.com/fonte",
        snippet=snippet,
        fetched_at=datetime(2026, 6, 1, tzinfo=UTC),
    )


def _pillar(pilar: AIMIPillar, score: int, with_ev: bool = True) -> PillarScore:
    return PillarScore(
        pilar=pilar,
        score=score,
        justificativa="justificativa de teste",
        evidencia=[_ev()] if with_ev else [],
    )


def _aimi(toptim_score: int = 4) -> AIMIScore:
    return AIMIScore(
        data_moat=_pillar(AIMIPillar.DATA_MOAT, 14),
        workflow_depth=_pillar(AIMIPillar.WORKFLOW_DEPTH, 16),
        technical_optimization=_pillar(
            AIMIPillar.TECHNICAL_OPTIMIZATION, toptim_score, with_ev=toptim_score > 6
        ),
        distribution_moat=_pillar(AIMIPillar.DISTRIBUTION_MOAT, 10),
        classificacao=Classification.AI_NATIVE,
    )


# --- faixas (RUBRICA §1) -------------------------------------------------------


@pytest.mark.parametrize(
    ("score", "band"),
    [
        (0, AIMIBand.AUSENTE),
        (6, AIMIBand.AUSENTE),
        (7, AIMIBand.EMERGENTE),
        (12, AIMIBand.EMERGENTE),
        (13, AIMIBand.ESTABELECIDO),
        (18, AIMIBand.ESTABELECIDO),
        (19, AIMIBand.FORTE),
        (25, AIMIBand.FORTE),
    ],
)
def test_band_for(score: int, band: AIMIBand) -> None:
    assert band_for(score) is band


# --- regra de evidência do AIMI (RUBRICA §0) ----------------------------------


def test_pillar_high_score_requires_evidence() -> None:
    with pytest.raises(ValidationError):
        PillarScore(
            pilar=AIMIPillar.DATA_MOAT,
            score=15,
            justificativa="sem evidência",
            evidencia=[],
        )


def test_pillar_low_score_allowed_without_evidence() -> None:
    p = PillarScore(
        pilar=AIMIPillar.DATA_MOAT, score=6, justificativa="sinais mínimos", evidencia=[]
    )
    assert p.band is AIMIBand.AUSENTE


def test_pillar_score_bounds() -> None:
    with pytest.raises(ValidationError):
        _pillar(AIMIPillar.DATA_MOAT, 26)


# --- AIMI total + identidade dos pilares --------------------------------------


def test_aimi_total_is_sum() -> None:
    aimi = _aimi(toptim_score=4)
    assert aimi.total == 14 + 16 + 4 + 10
    assert 0 <= aimi.total <= 100


def test_aimi_pillar_identity_enforced() -> None:
    with pytest.raises(ValidationError):
        AIMIScore(
            data_moat=_pillar(AIMIPillar.WORKFLOW_DEPTH, 10),  # pilar trocado
            workflow_depth=_pillar(AIMIPillar.WORKFLOW_DEPTH, 10),
            technical_optimization=_pillar(AIMIPillar.TECHNICAL_OPTIMIZATION, 4, with_ev=False),
            distribution_moat=_pillar(AIMIPillar.DISTRIBUTION_MOAT, 10),
            classificacao=Classification.AI_ENABLED,
        )


def test_inception_priority_optional_and_bounded() -> None:
    aimi = _aimi()
    assert aimi.inception_priority is None
    assert aimi.heuristic_version == "v0"
    # 101 está fora de 0–100; re-validar deve falhar (model_copy não revalida).
    with pytest.raises(ValidationError):
        AIMIScore.model_validate({**aimi.model_dump(), "inception_priority": 101})


# --- recomendação: evidência dos dois lados (F4.5) ----------------------------


def _rec(gap: bool = True, nvidia: bool = True) -> Recommendation:
    return Recommendation(
        tech="NIM",
        justificativa_tecnica="serving otimizado",
        justificativa_negocio="reduz custo de inferência",
        prioridade=Priority.ALTA,
        complexidade=Complexity.MEDIA,
        proxima_acao="testar NIM self-hosted",
        evidencia_gap=[_ev("100% API externa")] if gap else [],
        evidencia_nvidia=[_ev("NIM doc")] if nvidia else [],
    )


def test_recommendation_requires_both_sides() -> None:
    assert _rec().tech == "NIM"
    with pytest.raises(ValidationError):
        _rec(gap=False)
    with pytest.raises(ValidationError):
        _rec(nvidia=False)


# --- proveniência por campo no perfil -----------------------------------------


def test_profile_claim_provenance() -> None:
    profile = StartupProfile(
        nome="Acme AI",
        setor=Claim(value="fintech", evidence=[_ev()]),
        tecnologias=[Technology(nome="OpenAI API", categoria="LLM provider", evidence=[_ev()])],
    )
    assert profile.pais == "BR"  # escopo v1 (F1.10)
    assert profile.setor is not None and profile.setor.is_grounded
    assert len(profile.all_evidence) == 2


# --- estado do grafo: round-trip + import público -----------------------------


def test_graphstate_roundtrip_and_briefing() -> None:
    aimi = _aimi()
    briefing = Briefing(
        empresa="Acme AI",
        resumo_executivo="resumo",
        aimi=aimi,
        recomendacoes=[_rec()],
        acao_comercial="contatar via Inception",
    )
    state = GraphState(
        run_id="run-1",
        query="Acme AI",
        profile=StartupProfile(nome="Acme AI"),
        aimi=aimi,
        recommendations=[_rec()],
        briefing=briefing,
    )
    assert state.can_retry is True
    assert briefing.idioma == "pt-BR"  # F0.13
    # round-trip JSON completo (serializa todos os sub-modelos aninhados)
    restored = GraphState.model_validate_json(state.model_dump_json())
    assert restored.run_id == "run-1"
    assert restored.briefing is not None
    assert restored.briefing.aimi is not None
    assert restored.briefing.aimi.total == aimi.total
