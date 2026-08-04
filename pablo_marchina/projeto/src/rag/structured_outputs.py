from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.nvidia_client import NvidiaClient
from src.rag.schemas import RetrievedContext


class StructuredOutputGeneratorConfig(BaseModel):
    enabled: bool = True
    use_llm: bool = True


_NVIDIA_CLIENT: NvidiaClient | None = None


def _get_nvidia() -> NvidiaClient:
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        _NVIDIA_CLIENT = NvidiaClient()
    return _NVIDIA_CLIENT


class StructuredOutputGenerator:
    def __init__(self, config: Any | None = None) -> None:
        self.config = StructuredOutputGeneratorConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        schema: dict = kwargs.get("schema", {})
        for ctx in contexts:
            structured = self._extract_structured(ctx, schema)

            if structured:
                ctx.content = structured

        return contexts

    def _extract_structured(self, ctx: RetrievedContext, schema: dict) -> str | None:
        client = _get_nvidia()
        if self.config.use_llm and client.api_key:
            prompt = (
                f"Extract structured information from this chunk according to the schema.\n"
                f"Schema: {schema}\nChunk: {ctx.content[:1000]}\nStructured output:"
            )
            result = client.llm_generate(prompt, max_tokens=256)
            if result:
                return result
        return None
