from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class TableToGraphExtractorConfig(BaseModel):
    enabled: bool = True
    max_relations: int = 10


class TableToGraphExtractor:
    def __init__(self, config: Any | None = None) -> None:
        self.config = TableToGraphExtractorConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            relations = self._extract_relations(ctx)

            boost = min(len(relations) * 0.03, 0.15)

            ctx.relevance_score = round(min(ctx.relevance_score + boost, 1.0), 4)

        return contexts

    def _extract_relations(self, ctx: RetrievedContext) -> list[dict[str, str]]:
        content = ctx.content
        relations: list[dict[str, str]] = []
        lines = content.split("\n")
        for line in lines:
            if "|" in line:
                cells = [c.strip() for c in line.split("|") if c.strip()]
                if len(cells) >= 3:
                    relations.append(
                        {
                            "source": cells[0],
                            "relation": cells[1],
                            "target": cells[2],
                        }
                    )
            elif "\t" in line:
                cells = [c.strip() for c in line.split("\t") if c.strip()]
                if len(cells) >= 3:
                    relations.append(
                        {
                            "source": cells[0],
                            "relation": cells[1],
                            "target": cells[2],
                        }
                    )
        return relations[: self.config.max_relations]
