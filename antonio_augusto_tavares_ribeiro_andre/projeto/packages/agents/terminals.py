"""Briefings terminais — caminhos de saída que **não forçam recomendação NVIDIA** (F2.12 / F2.13).

Quando o diagnóstico não dá base para o fluxo normal (RAG → recomendação → benchmark), o grafo
encerra num briefing terminal, **sem alucinar**:

- **dados insuficientes (F2.12):** a evidência segue abaixo do piso de N fontes (F2.7) mesmo após
  o retry de coleta esgotar → briefing marcado `dados_insuficientes`, com o que foi apurado +
  as lacunas a cobrir. É o "não afirmar sobre fonte única" (princípio nº1 §8) levado ao desfecho.
- **fora de escopo (F2.13):** empresa `non-AI` de alta confiança → briefing `fora_de_escopo`
  (por que não é alvo Inception), sem recomendar tech NVIDIA à força. Distingue-se de "dados
  insuficientes": aqui *temos* corroboração e confiança — o descarte é uma decisão, não uma lacuna.

O **nó `briefing`** (F4.4, ver `nodes.py`) despacha para cá quando o `status` já chega terminal
(`INSUFFICIENT_DATA` / `OUT_OF_SCOPE`); o caminho normal — diagnóstico + recomendação — é da F4.4.
Determinista/offline: monta o briefing só com o que está no estado (ethos F2.14), sem rede/LLM.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from packages.schemas import Briefing, BriefingStatus, Classification

from .evidence_validator import MIN_SOURCES, evidence_sources

if TYPE_CHECKING:
    from packages.schemas import GraphState


def insufficient_data_briefing(state: GraphState, *, min_sources: int = MIN_SOURCES) -> Briefing:
    """Monta o briefing terminal **"dados insuficientes"** (F2.12) a partir do estado.

    Acionado pelo `evidence_validator` (F2.7): após o retry de coleta esgotar, a corroboração
    segue abaixo de `min_sources` hosts independentes. Em vez de classificar/recomendar sobre
    fonte única, o run encerra registrando **o que foi apurado** (nome, AIMI parcial se houver)
    e **as lacunas** — sem recomendação NVIDIA forçada e sem alucinar campos ausentes.
    """
    profile = state.profile
    empresa = (profile.nome if profile is not None else None) or state.query
    n_sources = len(evidence_sources(profile)) if profile is not None else 0

    lacunas = [
        f"corroboração insuficiente: {n_sources} fonte(s) independente(s) coletada(s), "
        f"abaixo do mínimo de {min_sources} para um diagnóstico confiável "
        f"(após {state.retry_count} retry(s) de coleta)."
    ]
    resumo = (
        f"Não foi possível reunir evidência independente suficiente sobre {empresa} para "
        "diagnosticar a maturidade com confiança. Em vez de classificar ou recomendar "
        "tecnologia NVIDIA a partir de fonte única, o run encerra como 'dados insuficientes', "
        "registrando o que foi apurado e as lacunas a cobrir."
    )

    return Briefing(
        empresa=empresa,
        status=BriefingStatus.DADOS_INSUFICIENTES,
        resumo_executivo=resumo,
        aimi=state.aimi,  # o que foi apurado (parcial / baixa confiança); pode ser None
        recomendacoes=[],  # terminal: nada de recomendação NVIDIA forçada
        lacunas=lacunas,
        run_id=state.run_id,
    )


def out_of_scope_briefing(state: GraphState) -> Briefing:
    """Monta o briefing terminal **"fora de escopo"** (F2.13) a partir do estado.

    Acionado pelo `evidence_validator` (F2.7) quando o diagnóstico tem corroboração (≥ N fontes)
    **e** o classifier (F2.6) cravou a classe `non-AI` com confiança (`is_confident_non_ai`).
    Em vez de forçar uma recomendação NVIDIA sobre quem não é alvo do Inception, o run encerra
    explicando **por que não é alvo** — classe `non-AI` + AIMI baixo, com a evidência que sustenta
    o diagnóstico — sem recomendação. O `aimi` é carregado (leva a classe e os sub-scores com
    evidência); determinista/offline, sem alucinar campos ausentes.
    """
    profile = state.profile
    empresa = (profile.nome if profile is not None else None) or state.query
    aimi = state.aimi
    classe = aimi.classificacao.value if aimi is not None else Classification.NON_AI.value
    total = f"{aimi.total}/100" if aimi is not None else "não calculado"

    resumo = (
        f"{empresa} foi classificada como {classe} com confiança (AIMI {total}), a partir de "
        "fontes independentes corroborantes. Por não ser uma empresa AI-native, não é alvo "
        "prioritário do NVIDIA Inception: em vez de forçar uma recomendação de tecnologia NVIDIA, "
        "o run encerra como 'fora de escopo', registrando o diagnóstico e a evidência que o "
        "sustenta."
    )

    return Briefing(
        empresa=empresa,
        status=BriefingStatus.FORA_DE_ESCOPO,
        resumo_executivo=resumo,
        aimi=aimi,  # diagnóstico fica (classe non-AI + AIMI baixo com evidência)
        recomendacoes=[],  # terminal: não força recomendação NVIDIA
        run_id=state.run_id,
    )


__all__ = ["insufficient_data_briefing", "out_of_scope_briefing"]
