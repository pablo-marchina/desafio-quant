"""hash of prompt config

Hypothesis: Evaluate whether hash of prompt config improves final product output without paid dependency.
Category: 8.44 Output Versioning and Audit
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class HashOfPromptConfig:
    """hash of prompt config"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        import hashlib
        import json

        prompt_config = json.dumps({k: str(v) for k, v in sorted(kwargs.items())}, sort_keys=True)

        if not getattr(self, "_prompt_config_hash", None):
            self._prompt_config_hash: str = ""

        self._prompt_config_hash = hashlib.sha256(prompt_config.encode()).hexdigest()

        return contexts
