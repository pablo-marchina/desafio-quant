"""Briefing executivo (F0.5).

Saída final do grafo (nó briefing, F4.4) — JSON + Markdown/PDF, **em PT-BR** (F0.13).
Próximas-ações nos **três eixos do §2**: comercial, técnica e comunitária (Inception).
`status` distingue o briefing normal do terminal de baixa confiança (F2.12) e do
"fora de escopo" para non-AI de alta confiança (F2.13).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .aimi import AIMIScore
from .enums import BriefingStatus
from .recommendation import Recommendation


class Briefing(BaseModel):
    """Relatório executivo de uma startup para o gerente do NVIDIA Inception."""

    model_config = ConfigDict(extra="forbid")

    empresa: str
    idioma: str = Field(default="pt-BR", description="Idioma de saída (F0.13).")
    status: BriefingStatus = BriefingStatus.NORMAL

    resumo_executivo: str
    aimi: AIMIScore | None = Field(
        default=None, description="Diagnóstico de maturidade (None se dados insuficientes)."
    )
    recomendacoes: list[Recommendation] = Field(default_factory=list)

    # Três eixos de próxima ação (§2). Em "fora de escopo"/"dados insuficientes"
    # podem vir vazios ou explicar a ausência de recomendação NVIDIA.
    acao_comercial: str | None = None
    acao_tecnica: str | None = None
    acao_comunitaria: str | None = Field(
        default=None, description="Onboarding/créditos/eventos/comunidade do Inception."
    )

    inception_priority: int | None = Field(
        default=None, ge=0, le=100, description="Prioridade de outreach (F6.13)."
    )

    # Preenchido quando status = DADOS_INSUFICIENTES (F2.12): o que faltou.
    lacunas: list[str] = Field(default_factory=list)

    run_id: str | None = None
    generated_at: datetime | None = None
