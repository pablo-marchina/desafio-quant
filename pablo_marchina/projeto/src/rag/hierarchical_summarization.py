from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.nvidia_client import NvidiaClient
from src.rag.schemas import RetrievedContext


class HierarchicalSummarizationConfig(BaseModel):
    enabled: bool = True
    min_chunks_per_group: int = 3
    max_summary_length: int = 500
    use_llm: bool = True


_NVIDIA_CLIENT: NvidiaClient | None = None


def _get_nvidia() -> NvidiaClient:
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        _NVIDIA_CLIENT = NvidiaClient()
    return _NVIDIA_CLIENT


class HierarchicalSummarization:
    def __init__(self, config: Any | None = None) -> None:
        self.config = HierarchicalSummarizationConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        groups: dict[str, list[RetrievedContext]] = {}
        for ctx in contexts:
            key = ctx.source_id or ctx.title
            groups.setdefault(key, []).append(ctx)
        summaries: list[RetrievedContext] = []
        for group in groups.values():
            if len(group) >= self.config.min_chunks_per_group:
                summary_text = self._summarize_group(group)
                best = max(group, key=lambda c: c.relevance_score)
                best.content = summary_text
                best.relevance_score = round(min(best.relevance_score + 0.05, 1.0), 4)
                summaries.append(best)
            else:
                summaries.extend(group)
        summaries.sort(key=lambda c: c.relevance_score, reverse=True)
        return summaries

    def _summarize_group(self, group: list[RetrievedContext]) -> str:
        client = _get_nvidia()
        if self.config.use_llm and client.api_key:
            texts = "\n---\n".join(c.content[:500] for c in group)
            prompt = (
                f"Summarize the following {len(group)} related chunks into {self.config.max_summary_length} chars:\n"
                f"{texts}\nSummary:"
            )
            result = client.llm_generate(prompt, max_tokens=self.config.max_summary_length)
            if result:
                return result
        combined = " ".join(c.content[:300] for c in group)
        return combined[: self.config.max_summary_length]
