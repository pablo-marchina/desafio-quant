from __future__ import annotations

import re
from urllib.parse import urlparse

from src.discovery.search_aggregator import SearchResult

# ── Signal definitions ────────────────────────────────────────────────────

_POSITIVE_CONTENT_SIGNALS: list[tuple[re.Pattern, float]] = [
    (re.compile(r"inteligência artificial|ia\b|artificial intelligence", re.IGNORECASE), 0.3),
    (re.compile(r"machine learning|deep learning|aprendizado de máquina", re.IGNORECASE), 0.3),
    (re.compile(r"startup|scale.?up|empreend", re.IGNORECASE), 0.2),
    (re.compile(r"brasil|brazil|brasileir|brazilian", re.IGNORECASE), 0.15),
    (re.compile(r"funding|seed|série [a-z]|investimento|rodada", re.IGNORECASE), 0.2),
    (re.compile(r"ai.?native|nativa.?ia|nativo.?ia", re.IGNORECASE), 0.4),
    (re.compile(r"LLM|NLP|generative|generativa|GPT|transformers", re.IGNORECASE), 0.25),
    (re.compile(r"GPU|CUDA|NVIDIA|acelera.?gpu", re.IGNORECASE), 0.3),
]

_NEGATIVE_CONTENT_SIGNALS: list[tuple[re.Pattern, float]] = [
    (re.compile(r"curso|evento|workshop|webinar|treinamento", re.IGNORECASE), -0.3),
    (re.compile(r"vaga|emprego|job|career|oportunidade", re.IGNORECASE), -0.2),
    (re.compile(r"receita|recipe|culinária|gastronomia", re.IGNORECASE), -0.4),
    (re.compile(r"futebol|esporte|esportivo|campeonato", re.IGNORECASE), -0.4),
    (re.compile(r"imóvel|apartamento|casa.*venda|aluguel", re.IGNORECASE), -0.4),
]

_POSITIVE_DOMAIN_SIGNALS: list[tuple[re.Pattern, float]] = [
    (re.compile(r"crunchbase\.com|angel\.co|linkedin\.com", re.IGNORECASE), 0.1),
    (re.compile(r"\.com\.br|\.br"), 0.05),
]


class RelevanceScorer:
    """Score search results by relevance to AI-native startup discovery.

    Higher scores indicate results more likely to be AI-native startups
    or relevant ecosystem information.
    """

    def score(self, result: SearchResult) -> float:
        """Return a relevance score in ``[0.0, 1.0]``."""
        score = 0.5  # neutral baseline

        # Content signals
        text = f"{result.title} {result.snippet}"
        for pattern, delta in _POSITIVE_CONTENT_SIGNALS:
            if pattern.search(text):
                score += delta

        for pattern, delta in _NEGATIVE_CONTENT_SIGNALS:
            if pattern.search(text):
                score += delta

        # Domain signals
        domain = urlparse(result.url).netloc
        for pattern, delta in _POSITIVE_DOMAIN_SIGNALS:
            if pattern.search(domain):
                score += delta

        # Boost from search engine rank (early results are more relevant)
        score += max(0, 0.1 - result.rank * 0.005)

        return max(0.0, min(1.0, score))

    def filter(self, results: list[SearchResult], min_score: float = 0.45) -> list[SearchResult]:
        """Filter and sort results by relevance score."""
        scored = [(self.score(r), r) for r in results]
        scored.sort(key=lambda x: -x[0])
        return [r for s, r in scored if s >= min_score]
