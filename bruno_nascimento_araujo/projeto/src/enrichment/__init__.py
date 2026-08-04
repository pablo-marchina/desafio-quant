"""Enriquecimento: filtragem semantica (QFirst), busca aberta e fallback SPA."""
from .search_provider import BaseSearchProvider, LinkExpansionProvider
from .semantic import QFirstScorer

__all__ = ["QFirstScorer", "BaseSearchProvider", "LinkExpansionProvider"]
