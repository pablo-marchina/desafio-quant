"""Inception Priority (F6.13): fila de outreach 0–100 = **potencial AI-native × upside NVIDIA**.

**Nível 2 do DSS** (ALINHAMENTO §9): transforma o diagnóstico AIMI (F2.6/F6.1) numa **fila
priorizada** de outreach para o gerente de Startups & VCs do NVIDIA Inception — não só
diagnósticos avulsos. Responde "quem abordo primeiro?" (§1: atrair, qualificar e nutrir).

O score deriva **só do AIMI** (sem GPU, puro/determinista) e é o produto de três fatores:

- **potencial AI-native** = (P1 Data Moat + P2 Workflow Depth) / 50 ∈ [0,1] — quão *real e
  defensável* é o negócio AI-native (moat de dado + profundidade de automação);
- **upside NVIDIA** = (25 − P3 Technical Optimization) / 25 ∈ [0,1] — quanto a graduação
  API→stack pode somar: **P3 baixo = stack imatura = maior upside** (RUBRICA §4 / ALINHAMENTO §8);
- **peso da classe** (§5.1) — `AI-native` 1.0, `AI-enabled` 0.5, `non-AI` 0.0 (fora do alvo).

O produto realiza a região **"alvo de graduação ★"** do plano `classe × AIMI` (ALINHAMENTO §5):
`AI-native` + **P1/P2 alto** + **P3 baixo** → topo da fila. Multiplicativo de propósito — exige
os **dois** lados: moat/workflow reais *e* upside de graduação; quem já internalizou a inferência
(P3 alto) cai no ranking porque o upside NVIDIA é menor, e um wrapper sem moat (P1/P2 baixo) cai
porque o potencial é menor. **Explicável** (§9): cada score sai com os fatores que o compõem.

Consumido pelo classifier (carimba `AIMIScore.inception_priority`, F0.5) e pelo briefing (F4.4,
que exibe o número + os fatores); a lista da UI (F5.4) ordena por ele — a fila do gerente.
"""

from __future__ import annotations

from packages.schemas import AIMIScore, Classification

#: Máximo do potencial AI-native = P1 (Data Moat) + P2 (Workflow Depth), 25 cada (RUBRICA §1).
POTENTIAL_MAX = 50
#: Máximo de P3 (Technical Optimization); o upside é o complemento (quanto falta internalizar).
OPT_MAX = 25

#: Peso da classe (§5.1): só `AI-native` é alvo pleno de graduação; `non-AI` está fora (ALINHAMENTO
#: §5). `AI-enabled` entra com meio peso — IA periférica tem menos upside de graduação NVIDIA.
CLASS_WEIGHT: dict[Classification, float] = {
    Classification.AI_NATIVE: 1.0,
    Classification.AI_ENABLED: 0.5,
    Classification.NON_AI: 0.0,
}


def inception_priority(aimi: AIMIScore) -> tuple[int, str]:
    """AIMI → `(prioridade 0–100, fatores)` — a fila de outreach do Inception (F6.13).

    `prioridade = 100 × peso(classe) × potencial × upside`, com `potencial = (P1+P2)/50` e
    `upside = (25−P3)/25` (ambos em [0,1]). Puro/determinista (sem rede/LLM/GPU). Devolve também
    os **fatores** em texto PT-BR auditável — a mesma conta que produz o número, para o briefing
    (§9 exige score explicável): nunca é caixa-preta.
    """
    p1 = aimi.data_moat.score
    p2 = aimi.workflow_depth.score
    p3 = aimi.technical_optimization.score
    potencial = (p1 + p2) / POTENTIAL_MAX
    upside = (OPT_MAX - p3) / OPT_MAX
    peso = CLASS_WEIGHT.get(aimi.classificacao, 0.0)
    score = max(0, min(100, round(100 * peso * potencial * upside)))
    fatores = (
        f"potencial AI-native {round(potencial * 100)}% (Data Moat {p1}/25 + Workflow Depth "
        f"{p2}/25) × upside de graduação {round(upside * 100)}% (Technical Optimization {p3}/25 — "
        f"quanto menor, maior o upside NVIDIA) × peso da classe {aimi.classificacao.value} "
        f"({peso:g}) = {score}/100"
    )
    return score, fatores


__all__ = ["inception_priority", "CLASS_WEIGHT", "POTENTIAL_MAX", "OPT_MAX"]
