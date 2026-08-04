from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def split_env_list(name: str, default: tuple[str, ...] = ()) -> tuple[str, ...]:
    raw = os.getenv(name, "")
    if not raw.strip():
        return default
    return tuple(item.strip() for item in re.split(r"[\n,]", raw) if item.strip())


FEEDS = split_env_list("RSS_NEWS_FEEDS")
KEYWORDS = split_env_list(
    "RSS_NEWS_KEYWORDS",
    (
        "startup",
        "startups",
        "inteligencia artificial",
        "ia",
        "ai",
        "machine learning",
        "llm",
        "fintech",
        "healthtech",
        "edtech",
        "hrtech",
        "deep tech",
        "saaS",
        "aporte",
        "rodada",
        "venture capital",
    ),
)
LOOKBACK_DAYS = int(os.getenv("RSS_NEWS_LOOKBACK_DAYS", "14"))
MAX_ENTRIES_PER_FEED = int(os.getenv("RSS_NEWS_MAX_ENTRIES_PER_FEED", "50"))
SOURCE_NAME = os.getenv("RSS_NEWS_SOURCE_NAME", "RSS News").strip() or "RSS News"
