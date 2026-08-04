"""Testes do mapa de regras gap → tech NVIDIA (F4.1) — a espinha do recommender (F4.2).

Tudo offline/determinista (sem rede/GPU/LLM). Exercita:

1. **Amarra à KB**: todo `kb_tech` das regras existe no manifesto (F3.1) como tech recomendável
   (`source_type: doc`) — adicionar uma regra com tech inexistente quebra o build (disciplina do
   `CORE_TECHS`/F3.1 e do mapa de queries/F3.8).
2. **Gap → tech** (`match_techs`): cada gap do AIMI (na ordem de severidade, mesma seleção do RAG)
   traz suas techs com `pilar_origem`; o setor (§5.5) anexa a tech de domínio; dedup determinístico.
3. **Aderência ao §5.5** (subconjunto — o ponta-a-ponta dos 7 exemplos é a F4.8): voz→Riva+NIM,
   dados tabulares→RAPIDS/cuDF/cuML, governança(P4)→Guardrails+NeMo, robotics→Isaac/Omniverse,
   latência(P3)→Triton/TensorRT-LLM.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from packages.agents import (
    PILLAR_RULES,
    SECTOR_RULES,
    match_sector,
    match_techs,
    recommendable_kb_techs,
    techs_for_pillar,
)
from packages.rag import load_kb_sources
from packages.schemas import (
    MAX_SCORE_WITHOUT_EVIDENCE,
    AIMIPillar,
    AIMIScore,
    Claim,
    Classification,
    Evidence,
    PillarScore,
    StartupProfile,
)

_FETCHED = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)


def _ev() -> Evidence:
    return Evidence(
        url="https://startup.example",
        snippet="trecho público",
        fetched_at=_FETCHED,
        content_hash="h1",
    )


def _claim(value: str) -> Claim[str]:
    return Claim[str](value=value, evidence=[_ev()])


def _pillar(pilar: AIMIPillar, score: int) -> PillarScore:
    ev = [_ev()] if score > MAX_SCORE_WITHOUT_EVIDENCE else []
    return PillarScore(pilar=pilar, score=score, justificativa="teste", evidencia=ev)


def _aimi(
    p1: int, p2: int, p3: int, p4: int, *, classe: Classification = Classification.AI_NATIVE
) -> AIMIScore:
    return AIMIScore(
        data_moat=_pillar(AIMIPillar.DATA_MOAT, p1),
        workflow_depth=_pillar(AIMIPillar.WORKFLOW_DEPTH, p2),
        technical_optimization=_pillar(AIMIPillar.TECHNICAL_OPTIMIZATION, p3),
        distribution_moat=_pillar(AIMIPillar.DISTRIBUTION_MOAT, p4),
        classificacao=classe,
    )


def _profile(setor: str | None = None, descricao: str | None = None) -> StartupProfile:
    return StartupProfile(
        nome="ACME",
        setor=_claim(setor) if setor is not None else None,
        descricao=_claim(descricao) if descricao is not None else None,
    )


def _techs(candidates) -> list[str]:
    return [c.rule.tech for c in candidates]


# --- Amarra à base de conhecimento (mesma disciplina do F3.1/F3.8) --------------------------


def test_every_rule_tech_exists_in_the_kb() -> None:
    # Toda tech recomendada tem de ser recuperável (existir na KB como `source_type: doc`).
    recomendaveis = {s.tech for s in load_kb_sources() if s.source_type == "doc"}
    faltando = recommendable_kb_techs() - recomendaveis
    assert not faltando, f"regras citam techs ausentes/não-recomendáveis na KB: {sorted(faltando)}"


def test_every_pillar_has_at_least_one_rule() -> None:
    # Nenhum gap fica sem prescrição (os 4 pilares mapeiam para ao menos uma tech).
    for pilar in AIMIPillar:
        assert techs_for_pillar(pilar), f"pilar sem regra de recomendação: {pilar.value}"


# --- Gap → tech ------------------------------------------------------------------------------


def test_gap_severity_orders_pillar_techs_with_origin() -> None:
    # P3 (4) e P2 (10) são gaps (≤12); P1/P4 estão estabelecidos. Ordem = menor score primeiro.
    cand = match_techs(_aimi(20, 10, 4, 22))
    pilares = [c.pilar_origem for c in cand]
    # P3 vem antes de P2; e cada candidata carrega o pilar que a motivou (rastreabilidade gap→tech).
    assert pilares[0] is AIMIPillar.TECHNICAL_OPTIMIZATION
    assert AIMIPillar.WORKFLOW_DEPTH in pilares
    assert all(p in (AIMIPillar.TECHNICAL_OPTIMIZATION, AIMIPillar.WORKFLOW_DEPTH) for p in pilares)
    assert "NVIDIA NIM" in _techs(cand)  # P3 → graduação


def test_mature_startup_gets_fallback_graduation_plus_enterprise() -> None:
    # Nenhum pilar ≤12: o fallback de gap_pillars guia pelo pilar mais baixo (P3=18 → graduação) E o
    # lever de maturidade (F7.7) acrescenta AI Enterprise — já graduou, a jogada é escala enterprise.
    cand = match_techs(_aimi(20, 22, 18, 24))
    techs = _techs(cand)
    assert "NVIDIA AI Enterprise" in techs  # lever de maturidade (AI-native, P3≥13)
    assert any(c.pilar_origem is AIMIPillar.TECHNICAL_OPTIMIZATION for c in cand)  # fallback de pilar


def test_graduated_ai_native_gets_enterprise_not_alvo() -> None:
    # F7.7 lever de maturidade: AI-native que já graduou (P3 estabelecido ≥13) recebe AI Enterprise
    # mesmo sem P4 ser gap. Um alvo de graduação (P3 baixo, P4 não-gap) NÃO recebe — ele grada.
    assert "NVIDIA AI Enterprise" in _techs(match_techs(_aimi(20, 18, 15, 20)))  # maduro
    assert "NVIDIA AI Enterprise" not in _techs(match_techs(_aimi(20, 18, 5, 20)))  # alvo


def test_ai_enabled_chat_surface_gets_guardrails() -> None:
    # F7.7 lever de governança: AI-enabled com superfície conversacional/generativa recebe NeMo
    # Guardrails (a feature gera texto livre), mesmo com a graduação suprimida pela classe. Uma
    # feature discriminativa (triagem/classificação) não pede governança de chat → segue sem nada.
    enabled = _aimi(7, 9, 4, 12, classe=Classification.AI_ENABLED)
    com_chat = match_techs(enabled, _profile(descricao="copiloto de dúvidas fiscais via chat LLM"))
    assert "NeMo Guardrails" in _techs(com_chat)
    sem_chat = match_techs(enabled, _profile(descricao="triagem de currículo via API de LLM"))
    assert "NeMo Guardrails" not in _techs(sem_chat)


def test_low_technical_optimization_triggers_graduation_even_when_not_lowest() -> None:
    # Acoplamento F6.3: P3 baixo DISPARA a recomendação de graduação (NIM/TensorRT-LLM/Triton),
    # mesmo quando P2/P4 (3/5) estão ainda mais baixos — pela severidade pura P3=12 cairia fora do
    # corte MAX_GAPS=3 e a graduação não dispararia. A F6.3 garante que dispara e lidera. P1=20 dá
    # core provado (não é wrapper puro), p/ o gate de wrapper frágil não suprimir a graduação.
    cand = match_techs(_aimi(20, 3, 12, 5))
    assert cand[0].pilar_origem is AIMIPillar.TECHNICAL_OPTIMIZATION  # P3 encabeça a prescrição
    assert "NVIDIA NIM" in _techs(cand)  # gatilho de graduação API→stack disparado


def test_unproven_wrapper_suppresses_graduation_keeps_sector() -> None:
    # Gate DSS §5 (wrapper frágil): AI-native com core ausente (P1≤6 E P2≤6) não recebe graduação
    # de infra (potencial não comprovado) — sem setor, nada a prescrever; com setor, só a tech de
    # domínio (a graduação segue suprimida). Distingue um wrapper puro de um alvo de graduação.
    assert match_techs(_aimi(2, 3, 4, 5)) == ()  # wrapper puro sem domínio → nada
    cand = match_techs(_aimi(2, 3, 4, 5), _profile(setor="Healthtech / saúde digital"))
    assert {c.rule.tech for c in cand} == {"NVIDIA Clara", "MONAI"}  # só setor
    assert all(c.pilar_origem is None for c in cand)  # nenhuma graduação de pilar


def test_ai_enabled_periferico_suppresses_graduation_keeps_sector() -> None:
    # Gate DSS §5 (periférico): num `AI-enabled` a IA não é o núcleo (baixa prioridade) — mesmo com
    # gaps de pilar **e core não-ausente** (P1/P2 > 6), a graduação de infra não dispara; só a tech
    # de setor (recebe setor por design, F4.8). Diferente do wrapper, aqui o gate é pela classe.
    aimi = _aimi(7, 9, 4, 12, classe=Classification.AI_ENABLED)  # P1/P2 > 6, P3 gap
    assert match_techs(aimi) == ()  # sem domínio → nada (graduação suprimida pela classe)
    cand = match_techs(aimi, _profile(setor="Healthtech / saúde digital"))
    assert {c.rule.tech for c in cand} == {"NVIDIA Clara", "MONAI"}
    assert all(c.pilar_origem is None for c in cand)


def test_sector_techs_are_appended_with_no_pillar_origin() -> None:
    cand = match_techs(_aimi(20, 22, 20, 24), _profile(setor="Healthtech / saúde digital"))
    setor = [c for c in cand if c.pilar_origem is None]
    assert {c.rule.tech for c in setor} >= {"NVIDIA Clara", "MONAI"}
    assert all(c.triggers == ("setor:saude",) for c in setor)


def test_no_profile_yields_only_pillar_techs() -> None:
    cand = match_techs(_aimi(4, 20, 20, 22), profile=None)
    assert all(c.pilar_origem is not None for c in cand)


def test_match_techs_is_deterministic() -> None:
    aimi = _aimi(4, 10, 4, 8)
    prof = _profile(setor="Voz e atendimento")
    assert match_techs(aimi, prof) == match_techs(aimi, prof)


# --- Aderência ao §5.5 (subconjunto; consolidação na F4.8) -----------------------------------


def test_voice_startup_maps_to_riva_and_nim() -> None:
    # §5.5: voz → Riva (setor) + NIM (gap de inferência P3).
    cand = match_techs(_aimi(20, 20, 4, 22), _profile(setor="Call center", descricao="bot de voz"))
    techs = _techs(cand)
    assert any("Riva" in t for t in techs)
    assert "NVIDIA NIM" in techs


def test_tabular_data_maps_to_rapids_stack() -> None:
    # §5.5: dados tabulares → RAPIDS/cuDF/cuML (eixo de setor exclusivo da F4.1).
    cand = match_techs(_aimi(20, 20, 20, 22), _profile(descricao="plataforma de analytics tabular"))
    assert {"NVIDIA RAPIDS", "cuDF", "cuML"} <= set(_techs(cand))


def test_governance_gap_maps_to_guardrails_and_nemo() -> None:
    # §5.5: governança → Guardrails + NeMo (avaliação). Gap de Distribution Moat (P4).
    cand = match_techs(_aimi(20, 20, 20, 4))
    techs = _techs(cand)
    assert "NeMo Guardrails" in techs
    assert any("NeMo Evaluator" in t for t in techs)
    assert all(c.pilar_origem is AIMIPillar.DISTRIBUTION_MOAT for c in cand)


def test_latency_gap_maps_to_triton_and_tensorrt() -> None:
    # §5.5: latência → Triton/TensorRT-LLM (gap de Technical Optimization P3).
    cand = match_techs(_aimi(20, 20, 3, 22))
    techs = _techs(cand)
    assert "TensorRT-LLM" in techs
    assert any("Triton" in t for t in techs)


def test_robotics_sector_maps_to_isaac_and_omniverse() -> None:
    cand = match_techs(_aimi(20, 20, 20, 22), _profile(setor="Robótica industrial"))
    setor = {c.rule.tech for c in cand if c.pilar_origem is None}
    assert {"NVIDIA Isaac", "NVIDIA Omniverse"} <= setor


# --- Tabelas de regra ------------------------------------------------------------------------


@pytest.mark.parametrize("pilar", list(AIMIPillar))
def test_pillar_rules_carry_full_recommendation_skeleton(pilar: AIMIPillar) -> None:
    # Cada regra já fecha o contrato §5.5 (F4.3) sem rede: campos não-vazios, esqueleto coerente.
    for rule in PILLAR_RULES[pilar]:
        assert rule.kb_tech and rule.tech
        assert rule.justificativa_tecnica and rule.justificativa_negocio and rule.proxima_acao


def test_sector_keys_are_unique() -> None:
    keys = [s.key for s in SECTOR_RULES]
    assert len(keys) == len(set(keys))


def test_match_sector_first_match_wins_and_none_when_empty() -> None:
    assert match_sector(None) is None
    assert match_sector(_profile()) is None  # sem setor/descrição → nada casa
    assert match_sector(_profile(setor="cibersegurança e fraude")).key == "ciberseguranca"
