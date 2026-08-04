from __future__ import annotations

import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)


class QueryGenerator:
    """Generate expanded search queries from seed terms.

    Uses an LLM (via environment-configured provider) to generate
    semantically related variants. Falls back to template-based
    expansion if no LLM is available.
    """

    def __init__(self, llm_client: Any | None = None):
        self._llm_client = llm_client

    def expand(self, seed_queries: list[str], n: int = 10) -> list[str]:
        """Return up to *n* expanded query variants."""
        if self._llm_client is not None:
            try:
                return self._llm_expand(seed_queries, n)
            except Exception as exc:
                logger.warning("LLM query expansion failed, using template fallback: %s", exc)

        return self._template_expand(seed_queries, n)

    def _llm_expand(self, seed_queries: list[str], n: int) -> list[str]:
        prompt = (
            "You are an expert in AI startup ecosystem research. "
            "Given the following seed search queries, generate up to "
            f"{n} alternative search queries that would help discover "
            "AI-native startups, their products, funding rounds, and "
            "technology stacks. Return one query per line, no numbering.\n\n"
            f"Seed queries:\n{chr(10).join(f'- {q}' for q in seed_queries)}"
        )
        response = self._llm_client.generate(prompt)
        lines = [line.strip() for line in response.splitlines() if line.strip()]
        return lines[:n]

    def _template_expand(self, seed_queries: list[str], n: int) -> list[str]:
        expanded: list[str] = []
        templates = [
            "{q} AI startup funding",
            "{q} machine learning company",
            "{q} inteligência artificial startup",
            "{q} LLM technology stack",
            "{q} deep learning product",
            "{q} NVIDIA partner startup",
            "{q} GPU acceleration",
            "{q} generative AI company",
        ]
        for sq in seed_queries:
            clean = re.sub(r"\s+", " ", sq).strip()
            for tmpl in templates:
                variant = tmpl.format(q=clean)
                if variant not in expanded:
                    expanded.append(variant)
                    if len(expanded) >= n:
                        break
            if len(expanded) >= n:
                break
        return expanded[:n]


def build_default_generator() -> QueryGenerator:
    """Build a QueryGenerator using the configured LLM client if available."""
    try:
        provider = os.environ.get("LLM_JUDGE_PROVIDER", "")
        if provider and provider != "disabled":
            from src.rag.nvidia_client import NVIDIAClient
            llm = NVIDIAClient()
            return QueryGenerator(llm_client=llm)
    except Exception as exc:
        logger.debug("Could not create LLM client for query generation: %s", exc)
    return QueryGenerator()
