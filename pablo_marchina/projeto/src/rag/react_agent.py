from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.nvidia_client import NvidiaClient
from src.rag.retrieval import ChunkIndex
from src.rag.schemas import RetrievalQuery, RetrievedContext

_REASONING_STEPS = [
    "analyze the query and identify key terms",
    "retrieve relevant information",
    "evaluate retrieved evidence for relevance",
    "synthesize findings",
    "formulate final response",
]


class ReActAgentConfig(BaseModel):
    enabled: bool = True
    max_steps: int = 5
    use_llm: bool = True


_NVIDIA_CLIENT: NvidiaClient | None = None


def _get_nvidia() -> NvidiaClient:
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        _NVIDIA_CLIENT = NvidiaClient()
    return _NVIDIA_CLIENT


class ReActAgent:
    def __init__(self, config: Any | None = None) -> None:
        self.config = ReActAgentConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query: str = kwargs.get("query", "")
        chunk_index: ChunkIndex | None = kwargs.get("chunk_index")
        seen_ids = {c.chunk_id for c in contexts}
        for step in range(self.config.max_steps):
            action = self._think(query, contexts, step)

            if not action or action == "finalize":
                break

            if chunk_index and action != "skip":
                more = chunk_index.retrieve(
                    RetrievalQuery(keywords=action.split()),
                    top_k=2,
                )

                for ctx in more:
                    if ctx.chunk_id not in seen_ids:
                        seen_ids.add(ctx.chunk_id)

                        contexts.append(ctx)

        return contexts

    def _think(self, query: str, contexts: list[RetrievedContext], step: int) -> str:
        client = _get_nvidia()
        if self.config.use_llm and client.api_key:
            ctx_summary = " ".join(c.content[:200] for c in contexts[-2:]) if contexts else "none"
            prompt = (
                f"Query: {query}\nStep: {step + 1}\nCurrent evidence: {ctx_summary}\n"
                f"What should the next action be? Either suggest search keywords, or say 'finalize'.\n"
                f"Action:"
            )
            result = client.llm_generate(prompt, max_tokens=32)
            if result and result.strip().lower() != "finalize":
                return result.strip()
        if step < len(_REASONING_STEPS):
            return f"search for {query}"
        return "finalize"
