"""Estado compartilhado do Extraction Graph."""

from typing import TypedDict

from apps.api.src.modules.agents.application.dto import (
    ExtractionInput,
    ExtractionResult,
)


class ExtractionState(TypedDict, total=False):
    """Estado minimo usado na V8 do Extraction Agent."""

    extraction_input: ExtractionInput
    prepared_context: str
    llm_result: ExtractionResult
    result: ExtractionResult
