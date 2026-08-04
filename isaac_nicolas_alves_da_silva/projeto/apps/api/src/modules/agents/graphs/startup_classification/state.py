"""Estado compartilhado do Startup Classification Graph."""

from typing import TypedDict

from apps.api.src.modules.agents.application.dto import (
    StartupClassificationInput,
    StartupClassificationResult,
)


class StartupClassificationState(TypedDict, total=False):
    """Estado minimo usado na V9 do Startup Classifier Agent."""

    classification_input: StartupClassificationInput
    prepared_context: str
    llm_result: StartupClassificationResult
    result: StartupClassificationResult
