"""Recommendation + ROI (F0.5).

Saída estruturada do §5.5 (nó recommender, F4.2/F4.3). Princípio "evidência dos
dois lados": `evidencia_gap` (lado startup — o que no perfil/AIMI motiva) **e**
`evidencia_nvidia` (citações da KB recuperadas pelo RAG). O contrato **exige ambos**
— é o mesmo invariante que o NeMo Guardrails (F4.5) reforça no briefing. `roi` é
opcional: vem do GPU Graduation Engine (F6) quando há gap de inferência (P3 baixo).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import AIMIPillar, Complexity, Priority
from .evidence import Evidence


class ROIEstimate(BaseModel):
    """ROI quantificado de migrar API → stack otimizada (GPU Graduation Engine, §5.3).

    Preenchido pela matriz de benchmark pré-computada (F6.9–F6.11). Todos os campos
    opcionais: a recomendação degrada graciosamente sem ROI (F5.6).
    """

    model_config = ConfigDict(extra="forbid")

    throughput_speedup: float | None = Field(
        default=None, ge=0, description="Ganho de throughput (ex.: 3.0 = 3x)."
    )
    latency_p95_delta_pct: float | None = Field(
        default=None, description="Variação de p95 (negativo = melhora)."
    )
    cost_delta_pct: float | None = Field(
        default=None, description="Variação de custo $/1M tokens (negativo = economia)."
    )
    baseline: str | None = Field(default=None, description="Linha de base (ex.: API externa).")
    optimized: str | None = Field(default=None, description="Alvo otimizado (ex.: NIM local).")
    benchmark_source: str | None = Field(
        default=None, description="Célula da matriz / referência do benchmark."
    )
    is_live_run: bool = Field(
        default=False, description="True se medido ao vivo na GPU (demo); False = matriz."
    )


class Recommendation(BaseModel):
    """Uma recomendação de tecnologia NVIDIA, no formato §5.5."""

    model_config = ConfigDict(extra="forbid")

    tech: str = Field(description="Tecnologia NVIDIA recomendada (ex.: NIM, TensorRT-LLM).")
    justificativa_tecnica: str
    justificativa_negocio: str
    prioridade: Priority
    complexidade: Complexity
    proxima_acao: str = Field(description="Próximo passo concreto para a startup.")

    # Pilar do AIMI que motivou a recomendação (rastreabilidade gap → tech, F4.1).
    pilar_origem: AIMIPillar | None = None

    # Evidência dos dois lados — ambos obrigatórios (Guardrails F4.5).
    evidencia_gap: list[Evidence] = Field(
        description="Lado startup: o que no perfil/AIMI motiva a recomendação."
    )
    evidencia_nvidia: list[Evidence] = Field(
        description="Lado NVIDIA: citações da KB recuperadas pelo RAG (F3.7)."
    )

    roi: ROIEstimate | None = Field(
        default=None, description="ROI quantificado quando há gap de inferência (F6)."
    )

    @model_validator(mode="after")
    def _require_both_sides(self) -> Recommendation:
        # Invariante central: recomendação sem um dos lados é inválida (F4.5).
        if not self.evidencia_gap:
            raise ValueError("recomendação exige `evidencia_gap` (lado startup).")
        if not self.evidencia_nvidia:
            raise ValueError("recomendação exige `evidencia_nvidia` (lado NVIDIA).")
        return self
