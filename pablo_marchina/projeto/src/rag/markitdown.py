from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_MD_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_MD_IMG = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_MD_TABLE = re.compile(r"^\|.+\|$", re.MULTILINE)
_MD_CODE = re.compile(r"```[\s\S]*?```", re.MULTILINE)


class Markitdown:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            links = len(_MD_LINK.findall(ctx.content))
            images = len(_MD_IMG.findall(ctx.content))
            tables = len(_MD_TABLE.findall(ctx.content))
            code = len(_MD_CODE.findall(ctx.content))
            ctx.content = f"[markitdown:links={links} images={images} tables={tables} code={code}]\n{ctx.content}"
        return contexts
