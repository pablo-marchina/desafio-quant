from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class SourceType(str, Enum):
    PUBLIC_DIRECTORY = "public_directory"
    STARTUP_PROGRAM = "startup_program"
    NEWS = "news"
    ACCELERATOR = "accelerator"
    VC_PORTFOLIO = "vc_portfolio"
    EVENT_PAGE = "event_page"
    SEARCH_API = "search_api"
    MANUAL_SEED = "manual_seed"


class CollectionMethod(str, Enum):
    MANUAL_SEED = "manual_seed"
    URL_LIST = "url_list"
    STATIC_HTML = "static_html"
    OPTIONAL_PLAYWRIGHT = "optional_playwright"
    OPTIONAL_SEARCH_API = "optional_search_api"


@dataclass
class DiscoverySource:
    source_id: str
    name: str
    source_type: SourceType
    base_url: str = ""
    country_scope: str = "Brazil"
    sector_scope: str = ""
    allowed: bool = True
    requires_api_key: bool = False
    rate_limit_hint: int = 5
    collection_method: CollectionMethod = CollectionMethod.MANUAL_SEED
    robots_or_terms_note: str = ""
    enabled_by_default: bool = True
    notes: str = ""

    def is_usable(self, *, api_key_available: bool = False) -> bool:
        if not self.allowed:
            return False
        if self.requires_api_key and not api_key_available:
            return False
        return True


_DEFAULT_SOURCE_PATH = "src/config/discovery_sources.json"
_sources_cache: dict[str, DiscoverySource] | None = None


def get_source_config_path() -> str:
    return os.getenv(
        "DISCOVERY_SOURCE_CONFIG_PATH",
        str(Path(__file__).resolve().parent.parent / "config" / "discovery_sources.json"),
    )


def load_sources(source_path: str | None = None) -> dict[str, DiscoverySource]:
    global _sources_cache
    if _sources_cache is not None and source_path is None:
        return _sources_cache

    path = source_path or get_source_config_path()
    p = Path(path)
    if not p.exists():
        _sources_cache = {}
        return _sources_cache

    raw = json.loads(p.read_text(encoding="utf-8"))
    sources: dict[str, DiscoverySource] = {}
    for item in raw:
        source = DiscoverySource(
            source_id=str(item["source_id"]),
            name=str(item.get("name", "")),
            source_type=SourceType(item.get("source_type", "manual_seed")),
            base_url=str(item.get("base_url", "")),
            country_scope=str(item.get("country_scope", "Brazil")),
            sector_scope=str(item.get("sector_scope", "")),
            allowed=bool(item.get("allowed", True)),
            requires_api_key=bool(item.get("requires_api_key", False)),
            rate_limit_hint=int(item.get("rate_limit_hint", 5)),
            collection_method=CollectionMethod(item.get("collection_method", "manual_seed")),
            robots_or_terms_note=str(item.get("robots_or_terms_note", "")),
            enabled_by_default=bool(item.get("enabled_by_default", True)),
            notes=str(item.get("notes", "")),
        )
        sources[source.source_id] = source

    if source_path is None:
        _sources_cache = sources
    return sources


def get_source(source_id: str) -> DiscoverySource | None:
    return load_sources().get(source_id)


def list_enabled_sources(*, api_key_available: bool = False) -> list[DiscoverySource]:
    return [s for s in load_sources().values() if s.is_usable(api_key_available=api_key_available)]


def reset_source_cache() -> None:
    global _sources_cache
    _sources_cache = None
