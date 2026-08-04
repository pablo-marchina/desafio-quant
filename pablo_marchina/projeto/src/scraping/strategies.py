"""Collector strategy registry that dispatches each source to the correct
fetcher/collector based on its ``collector_type`` and ``source_category``.

Extends the inline dispatch dict in ``collector.py`` with pluggable strategies
for YouTube, RSS, PDF, and JS-heavy (Playwright/crawl4ai) sources.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from src.scraping.source_registry import SourceRecord

logger = logging.getLogger(__name__)

CollectorFn = Callable[..., Coroutine[Any, Any, Any] | Any]

_STRATEGIES: dict[str, CollectorFn] = {}


def register(category_or_type: str) -> Callable[[CollectorFn], CollectorFn]:
    """Decorator to register a collector strategy for a category/collector type.

    Usage::

        @register("youtube")
        async def collect_youtube(source: SourceRecord) -> ...:
            ...
    """

    def wrapper(fn: CollectorFn) -> CollectorFn:
        _STRATEGIES[category_or_type] = fn
        logger.debug("STRATEGY registered  %s -> %s", category_or_type, fn.__name__)
        return fn

    return wrapper


def resolve(source: SourceRecord) -> CollectorFn | None:
    """Return the collector function for *source*, or ``None``.

    Priority:
      1. ``collector_type`` (e.g. ``"youtube"``, ``"rss"``, ``"pdf"``)
      2. ``source_category`` (e.g. ``"official_website"``)
    """
    ct = source.collector_type
    if ct and ct in _STRATEGIES:
        return _STRATEGIES[ct]
    cat = source.source_category
    if cat in _STRATEGIES:
        return _STRATEGIES[cat]
    return None


def resolve_and_call(source: SourceRecord) -> Any:
    """Resolve and call the strategy for *source*, handling both sync and async functions.

    If the registered strategy is a coroutine function, it is executed via
    ``asyncio.run()``.  Otherwise it is called synchronously.
    Returns ``None`` when no strategy is registered.
    """
    fn = resolve(source)
    if fn is None:
        return None
    if inspect.iscoroutinefunction(fn):
        return asyncio.run(fn(source))
    return fn(source)


def registered_strategies() -> dict[str, str]:
    """Return ``{key: function_name}`` for all registered strategies."""
    return {k: v.__name__ for k, v in _STRATEGIES.items()}
