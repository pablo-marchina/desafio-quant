"""AIMIScore — AI-Native Maturity Index (F0.5).

Contrato de saída do `classifier` (v0, F2.6) e da heurística refinada (v1, F6.1).
A **definição** (pilares + escala 0–25) vive em `docs/ARQUITETURA.md §3.6` (F0.11) e é
imutável; só a heurística que preenche os números evolui — por isso `heuristic_version`
é carimbado aqui. Regra de evidência (RUBRICA §0): sub-score > 6 exige evidência.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import AIMIBand, AIMIPillar, Classification
from .evidence import Evidence

#: Teto de pontos permitido a um pilar sem evidência citável (RUBRICA §0: faixa
#: "sinais públicos mínimos"). Score alto sem evidência é bloqueado, não suposto.
MAX_SCORE_WITHOUT_EVIDENCE = 6


def band_for(score: int) -> AIMIBand:
    """Mapeia um sub-score 0–25 para a faixa genérica (RUBRICA §1)."""
    if score <= 6:
        return AIMIBand.AUSENTE
    if score <= 12:
        return AIMIBand.EMERGENTE
    if score <= 18:
        return AIMIBand.ESTABELECIDO
    return AIMIBand.FORTE


class PillarScore(BaseModel):
    """Sub-score de um pilar (0–25) + a evidência que o sustenta."""

    model_config = ConfigDict(extra="forbid")

    pilar: AIMIPillar
    score: int = Field(ge=0, le=25)
    justificativa: str = Field(description="Por que o pilar recebeu este score.")
    evidencia: list[Evidence] = Field(default_factory=list)
    #: Faixa derivada do score (RUBRICA §1). Sempre recomputada do `score` no
    #: validator — campo real (não computed_field) para fazer round-trip JSON com
    #: `extra="forbid"` (estado serializado pelo checkpointer, F2.2).
    band: AIMIBand | None = None

    @model_validator(mode="after")
    def _derive_band_and_enforce_evidence(self) -> PillarScore:
        # Faixa é sempre função do score (ignora valor recebido — fonte única).
        self.band = band_for(self.score)
        # RUBRICA §0: sem evidência citável, o sub-score não passa de ≤6.
        if self.score > MAX_SCORE_WITHOUT_EVIDENCE and not self.evidencia:
            raise ValueError(
                f"pilar {self.pilar.value}: score {self.score} > "
                f"{MAX_SCORE_WITHOUT_EVIDENCE} exige ao menos uma evidência."
            )
        return self


class AIMIScore(BaseModel):
    """Diagnóstico de maturidade AI-native: 4 pilares × 0–25 → total 0–100.

    Inclui a classe (§5.1) e o `inception_priority` (F6.13) — campo já no contrato,
    mas só calculado na F6 (default None até lá).
    """

    model_config = ConfigDict(extra="forbid")

    data_moat: PillarScore
    workflow_depth: PillarScore
    technical_optimization: PillarScore
    distribution_moat: PillarScore

    classificacao: Classification
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    inception_priority: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Prioridade de outreach 0–100 (F6.13); None até a F6 calcular.",
    )
    heuristic_version: str = Field(
        default="v0",
        description="Versão da heurística de pontuação (v0 F2.6 → v1 F6.1).",
    )
    #: AIMI total 0–100 = soma dos 4 pilares. Recomputado no validator (campo real
    #: p/ round-trip JSON com `extra="forbid"`; o valor recebido é ignorado).
    total: int = Field(default=0, ge=0, le=100)

    @model_validator(mode="after")
    def _check_pillars_and_total(self) -> AIMIScore:
        # Garante que cada campo carrega o pilar correto (evita troca silenciosa).
        expected = {
            "data_moat": AIMIPillar.DATA_MOAT,
            "workflow_depth": AIMIPillar.WORKFLOW_DEPTH,
            "technical_optimization": AIMIPillar.TECHNICAL_OPTIMIZATION,
            "distribution_moat": AIMIPillar.DISTRIBUTION_MOAT,
        }
        for field, pilar in expected.items():
            if getattr(self, field).pilar is not pilar:
                raise ValueError(f"campo {field} deve conter o pilar {pilar.value}.")
        # Total é sempre a soma dos pilares (fonte única de verdade).
        self.total = sum(p.score for p in self.pillars)
        return self

    @property
    def pillars(self) -> list[PillarScore]:
        return [
            self.data_moat,
            self.workflow_depth,
            self.technical_optimization,
            self.distribution_moat,
        ]
