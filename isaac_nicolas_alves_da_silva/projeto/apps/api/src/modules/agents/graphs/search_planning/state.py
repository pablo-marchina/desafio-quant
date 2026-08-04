"""Estado compartilhado do Search Planning Graph."""

from typing import TypedDict

from apps.api.src.modules.agents.application.dto import (
    SearchPlanInput,
    SearchPlanResult,
)


class SearchPlanningState(TypedDict, total=False):
    """Estado minimo usado na V3 do Search Planner Agent."""

    plan_input: SearchPlanInput
    prepared_context: str
    llm_plan: SearchPlanResult
    result: SearchPlanResult
