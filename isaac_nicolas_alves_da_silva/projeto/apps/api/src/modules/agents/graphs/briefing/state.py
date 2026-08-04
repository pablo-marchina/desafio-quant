"""Estado compartilhado do Briefing Graph."""

from typing import TypedDict
from uuid import UUID

from apps.api.src.modules.agents.application.dto import (
    BriefingAgentInput,
    BriefingAgentResult,
)


class BriefingState(TypedDict, total=False):
    """Estado minimo usado na V12 do Briefing Agent."""

    briefing_input: BriefingAgentInput
    prepared_context: str
    deterministic_content: str
    rewritten_content: str
    briefing_id: UUID
    result: BriefingAgentResult
