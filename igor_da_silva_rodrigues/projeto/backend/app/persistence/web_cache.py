from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from app.persistence.persistence_service import PipelinePersistence


_batch_run_id: ContextVar[str | None] = ContextVar("web_batch_run_id", default=None)
_pipeline_run_id: ContextVar[str | None] = ContextVar("web_pipeline_run_id", default=None)
_startup_name: ContextVar[str | None] = ContextVar("web_startup_name", default=None)
FIRECRAWL_OPTIONS = {"formats": ["markdown"], "onlyMainContent": True}


class SupabaseWebContentCache:
    """Seven-day cache and usage ledger for paid web extraction calls."""

    def __init__(self, persistence: PipelinePersistence, ttl_seconds: int = 604800) -> None:
        self.persistence = persistence
        self.db = persistence.db
        self.ttl_seconds = ttl_seconds

    def get(self, url: str, extractor: str = "firecrawl") -> dict[str, Any] | None:
        cache_key = _cache_key(url, extractor)
        response = (
            self.db.table("web_content_cache")
            .select("response_json,expires_at")
            .eq("cache_key", cache_key)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if not rows:
            return None
        expires_at = datetime.fromisoformat(str(rows[0]["expires_at"]).replace("Z", "+00:00"))
        if expires_at <= datetime.now(UTC):
            return None
        return rows[0]["response_json"]

    def set(self, url: str, value: dict[str, Any], extractor: str = "firecrawl") -> None:
        self.db.table("web_content_cache").upsert(
            {
                "cache_key": _cache_key(url, extractor),
                "url": url,
                "extractor": extractor,
                "options_hash": _options_hash(FIRECRAWL_OPTIONS),
                "response_json": value,
                "expires_at": (datetime.now(UTC) + timedelta(seconds=self.ttl_seconds)).isoformat(),
            },
            on_conflict="cache_key",
        ).execute()

    def record_usage(
        self,
        url: str,
        cache_hit: bool,
        success: bool,
        estimated_cost_usd: float = 0.0,
        reservation_id: str | None = None,
        operation: str = "scrape",
    ) -> None:
        payload = {
            "provider": "firecrawl",
            "operation": operation,
            "source_domain": urlparse(url).netloc.lower() or None,
            "batch_run_id": _batch_run_id.get(),
            "pipeline_run_id": _pipeline_run_id.get(),
            "startup_name": _startup_name.get(),
            "units": 0 if cache_hit else 1,
            "estimated_cost_usd": 0.0 if cache_hit else estimated_cost_usd,
            "cache_hit": cache_hit,
            "success": success,
        }
        if reservation_id:
            self.db.table("external_api_usage").update(
                {"success": success, "source_domain": payload["source_domain"]}
            ).eq("id", reservation_id).execute()
            return
        self.db.table("external_api_usage").insert(payload).execute()

    def reserve_request(
        self,
        url: str,
        limit: int,
        estimated_cost_usd: float = 0.0,
        operation: str = "scrape",
    ) -> dict[str, Any]:
        response = self.db.rpc(
            "reserve_external_api_usage",
            {
                "p_provider": "firecrawl",
                "p_operation": operation,
                "p_url": url,
                "p_batch_run_id": _batch_run_id.get(),
                "p_pipeline_run_id": _pipeline_run_id.get(),
                "p_startup_name": _startup_name.get(),
                "p_limit": limit,
                "p_estimated_cost_usd": estimated_cost_usd,
            },
        ).execute()
        data = response.data or {}
        if isinstance(data, list):
            data = data[0] if data else {}
        return dict(data)


def _cache_key(url: str, extractor: str) -> str:
    options = _options_hash(FIRECRAWL_OPTIONS)
    return hashlib.sha256(f"v2:{extractor}:{options}:{url.strip()}".encode("utf-8")).hexdigest()


def _options_hash(options: dict[str, Any]) -> str:
    content = json.dumps(options, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@contextmanager
def web_usage_context(batch_run_id: str, startup_name: str):
    batch_token = _batch_run_id.set(batch_run_id)
    startup_token = _startup_name.set(startup_name)
    pipeline_token = _pipeline_run_id.set(None)
    try:
        yield
    finally:
        _pipeline_run_id.reset(pipeline_token)
        _startup_name.reset(startup_token)
        _batch_run_id.reset(batch_token)


def set_web_pipeline_run_id(run_id: str) -> None:
    _pipeline_run_id.set(run_id)
