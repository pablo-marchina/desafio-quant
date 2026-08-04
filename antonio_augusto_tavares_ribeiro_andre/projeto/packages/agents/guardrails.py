"""NeMo Guardrails no briefing (F4.5) — **output rail de evidência**: recomendação só com 2 lados.

Último guard antes do relatório sair (nó `briefing`, F4.4): reforça o **invariante central** do TAPI
— nenhuma recomendação NVIDIA sem **`evidencia_gap` E `evidencia_nvidia`** (o mesmo
`Recommendation._require_both_sides` do schema, F0.5). É a defesa em profundidade do princípio de
evidência (§8): o recommender (F4.2) já só emite o que tem os dois lados, mas o rail **revalida** a
saída — pega qualquer recomendação montada fora da validação (ex.: `model_construct`, refino LLM
futuro, ingestão externa) e a **descarta** antes de virar texto do briefing, em vez de alucinar.

**Decisão de design (espinha verde, igual a todo o F3/F4):** o veredito do rail é **determinista**.
O invariante dos dois lados é uma **regra dura** — não um juízo de modelo: delegá-lo a um LLM
reintroduziria justamente a alucinação que ele existe para barrar. Por isso `check_recommendations`
(offline, sem rede/GPU) é a fonte de verdade e o **default**. O **NeMo Guardrails** entra como a
camada de **orquestração de produção** (Colang + custom action em `guardrails_config/`), plugável
atrás de `settings.briefing_use_guardrails` **ou** de um adapter `guard=` injetado, com import
preguiçoso — o módulo importa offline no Windows sem `nemoguardrails` (dep adiada: puxa `annoy`/C++,
roda só no container Linux/GPU). Mesmo no caminho NeMo o **veredito continua determinista** (o
custom action reusa `check_recommendations`): o NeMo abriga o rail (e os rails futuros de
diálogo/jailbreak), mas nunca decide se há evidência. Qualquer falha (dep ausente, config inválida)
**degrada p/ a espinha** — o rail nunca deixa de rodar.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from packages.config import get_settings
from packages.schemas import Recommendation

#: Diretório da config NeMo Guardrails (Colang + actions) — orquestração de produção (container).
GUARDRAILS_CONFIG = Path(__file__).parent / "guardrails_config"

#: Motivos legíveis do bloqueio (entram no trace do nó + log do rail) — um por lado faltante.
GAP_MISSING = "sem evidencia_gap (lado startup)"
NVIDIA_MISSING = "sem evidencia_nvidia (lado NVIDIA)"

# Adapter injetável: recomendações -> veredito. Default = espinha determinista; NeMo plugável.
GuardFn = Callable[[Sequence[Recommendation]], "GuardrailReport"]


def evidence_violations(rec: Recommendation) -> list[str]:
    """Violações do invariante dos dois lados numa recomendação (lista vazia = aprovada).

    O **núcleo** do rail (F4.5): bloqueia se faltar `evidencia_gap` (lado startup) **ou**
    `evidencia_nvidia` (lado NVIDIA) — o mesmo `Recommendation._require_both_sides` (F0.5), aqui
    como verificação independente da saída (pega rec montada fora da validação). Determinístico.
    """
    motivos: list[str] = []
    if not rec.evidencia_gap:
        motivos.append(GAP_MISSING)
    if not rec.evidencia_nvidia:
        motivos.append(NVIDIA_MISSING)
    return motivos


class BlockedRecommendation(BaseModel):
    """Recomendação barrada pelo rail, com o(s) lado(s) de evidência faltante(s) (p/ auditoria)."""

    model_config = ConfigDict(extra="forbid")

    tech: str
    motivos: list[str] = Field(
        description="Lados de evidência faltantes (GAP_MISSING/NVIDIA_MISSING)."
    )


class GuardrailReport(BaseModel):
    """Veredito do rail: recomendações aprovadas × bloqueadas (com motivo) — base do trace/log."""

    model_config = ConfigDict(extra="forbid")

    aprovadas: list[Recommendation] = Field(default_factory=list)
    bloqueadas: list[BlockedRecommendation] = Field(default_factory=list)

    @property
    def passou(self) -> bool:
        """`True` se nenhuma recomendação foi bloqueada (todas têm evidência dos dois lados)."""
        return not self.bloqueadas

    def trace(self) -> dict:
        """Resumo serializável p/ `state.trace["guardrails"]` (observabilidade do rail, F0.8)."""
        return {
            "n_aprovadas": len(self.aprovadas),
            "n_bloqueadas": len(self.bloqueadas),
            "bloqueadas": [b.model_dump() for b in self.bloqueadas],
        }


def check_recommendations(recs: Sequence[Recommendation]) -> GuardrailReport:
    """Espinha determinista do rail: separa aprovadas × bloqueadas pelo invariante dos dois lados.

    Preserva a ordem de entrada (herda a do recommender, F4.2). Sem rede/LLM/GPU — reprodutível.
    É a **fonte de verdade** do veredito (também o custom action do caminho NeMo, anti-alucinação).
    """
    aprovadas: list[Recommendation] = []
    bloqueadas: list[BlockedRecommendation] = []
    for rec in recs:
        motivos = evidence_violations(rec)
        if motivos:
            bloqueadas.append(BlockedRecommendation(tech=rec.tech, motivos=motivos))
        else:
            aprovadas.append(rec)
    return GuardrailReport(aprovadas=aprovadas, bloqueadas=bloqueadas)


def _nemo_guard(recs: Sequence[Recommendation]) -> GuardrailReport:
    """Caminho **NeMo Guardrails** (F4.5) — orquestração de produção (container Linux/GPU).

    Carrega o rail config (Colang + custom action em `guardrails_config/`) via
    `RailsConfig.from_path` — o que **valida** a config e registra a action no container — e devolve
    o veredito. A decisão é **determinista** (`check_recommendations`, o mesmo
    `check_recommendation_evidence` do `actions.py`): o invariante dos dois lados é regra dura, não
    juízo do LLM (anti-alucinação). Import preguiçoso: o módulo importa offline no Windows sem a dep
    (ver memória dev-env); o caller captura qualquer falha e cai na espinha determinista.
    """
    from nemoguardrails import RailsConfig  # dep adiada (annoy/C++) — só no container

    RailsConfig.from_path(str(GUARDRAILS_CONFIG))  # valida o Colang/actions do rail no container
    return check_recommendations(recs)  # veredito determinista (o custom action reusa esta função)


def guard_recommendations(
    recs: Sequence[Recommendation], *, guard: GuardFn | None = None
) -> GuardrailReport:
    """Aplica o rail de evidência (F4.5): espinha determinista por padrão; NeMo se ligado, c/ queda.

    Sempre roda (é uma invariante de segurança, não um opt-in): o flag/adapter só escolhe **como**
    orquestrar. `guard=` injetado (testes/worker) tem precedência; senão,
    `settings.briefing_use_guardrails` liga o NeMo Guardrails (container), caindo na espinha
    determinista a qualquer falha (dep/config).
    """
    if guard is not None:
        return guard(recs)
    if not get_settings().briefing_use_guardrails:
        return check_recommendations(recs)  # default offline/determinista (reproduzível)
    try:
        return _nemo_guard(recs)
    except Exception:  # noqa: BLE001 — nemoguardrails ausente/config inválida → espinha determinista
        return check_recommendations(recs)


__all__ = [
    "GUARDRAILS_CONFIG",
    "GAP_MISSING",
    "NVIDIA_MISSING",
    "GuardFn",
    "BlockedRecommendation",
    "GuardrailReport",
    "evidence_violations",
    "check_recommendations",
    "guard_recommendations",
]
