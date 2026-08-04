"""Custom action do output rail de evidência (F4.5) — registrado pelo NeMo Guardrails no container.

Este módulo é descoberto/importado **pelo NeMo Guardrails** (`RailsConfig.from_path`) no container
Linux/GPU — nunca pelo pacote `packages.agents` (que importa offline no Windows sem a dep). A action
**reusa a espinha determinista** (`check_recommendations`): o veredito do rail é a mesma regra dura
dos dois lados, então o NeMo orquestra o fluxo mas o LLM nunca decide se há evidência
(anti-alucinação — o ethos de todo o F4).
"""

from __future__ import annotations

from typing import Any

from nemoguardrails.actions import action

from packages.agents.guardrails import check_recommendations
from packages.schemas import Recommendation


@action(name="check_recommendation_evidence")
async def check_recommendation_evidence(recommendations: list[Any] | None = None) -> bool:
    """`True` se TODA recomendação tem `evidencia_gap` E `evidencia_nvidia` (rail passa).

    As recomendações chegam do contexto do rail (`$recommendations`). Delega o veredito à espinha
    determinista `check_recommendations` (F4.5) — a mesma regra do caminho offline.
    """
    recs = [Recommendation.model_validate(r) for r in (recommendations or [])]
    return check_recommendations(recs).passou
