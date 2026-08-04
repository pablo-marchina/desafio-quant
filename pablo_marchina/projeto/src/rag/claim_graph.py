from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_ENTITY_KEYWORDS = re.compile(
    r"(NVIDIA|CUDA|TensorRT|Triton|NeMo|RAPIDS|Morpheus|cuOpt|cuQuantum|"
    r"cuDNN|cuBLAS|cuSPARSE|TensorCore|GPU|DPU|Grace|Hopper|Blackwell|"
    r"Ampere|Jetson|Drive|Clara|Isaac|Merlin|Maxine|Aerial|AI\s*Enterprise)"
)


class ClaimGraph:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            entities_per_context: list[set[str]] = []
            for ctx in contexts:
                entities = set(_ENTITY_KEYWORDS.findall(ctx.content))

                entities_per_context.append(entities)

                for i, ctx in enumerate(contexts):
                    connection_count = 0

                    for j, other_entities in enumerate(entities_per_context):
                        if i != j and entities_per_context[i] & other_entities:
                            connection_count += 1

                            if connection_count > 0:
                                ctx.relevance_score = round(
                                    ctx.relevance_score * (1.0 + 0.05 * min(connection_count, 5)), 4
                                )

        return contexts
