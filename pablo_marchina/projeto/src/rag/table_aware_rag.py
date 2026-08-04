from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class TableAwareRAGConfig(BaseModel):
    enabled: bool = True
    boost_for_tables: float = 0.15


class TableAwareRAG:
    def __init__(self, config: Any | None = None) -> None:
        self.config = TableAwareRAGConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            tables = self._extract_tables(ctx.content)

            if tables:
                ctx.relevance_score = round(min(ctx.relevance_score + self.config.boost_for_tables, 1.0), 4)

                ctx.content = self._serialize_tables(ctx.content, tables)

        return contexts

    @staticmethod
    def _extract_tables(content: str) -> list[list[str]]:
        tables: list[list[str]] = []
        lines = content.split("\n")
        in_table = False
        current: list[str] = []
        for line in lines:
            if "|" in line and line.count("|") >= 2:
                cells = [c.strip() for c in line.split("|") if c.strip()]
                if len(cells) >= 2:
                    current.append(" | ".join(cells))
                    in_table = True
                    continue
            if in_table:
                if current:
                    tables.append(current)
                    current = []
                in_table = False
        if in_table and current:
            tables.append(current)
        return tables

    @staticmethod
    def _serialize_tables(content: str, tables: list[list[str]]) -> str:
        result = content
        for table in tables:
            serialized = "\n".join(table)
            if serialized in result:
                result = result.replace(
                    "\n".join(content.split("\n")[content.split("\n").index(table[0]) :][: len(table)]),
                    f"[TABLE]\n{serialized}\n[/TABLE]",
                    1,
                )
        return result
