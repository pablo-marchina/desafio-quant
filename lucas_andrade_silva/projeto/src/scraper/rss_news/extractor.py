from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

COMPANY_TRIGGER = (
    "startup",
    "fintech",
    "healthtech",
    "edtech",
    "hrtech",
    "empresa",
    "companhia",
)
ACTION_TRIGGER = (
    "recebe",
    "capta",
    "levanta",
    "anuncia",
    "lanca",
    "usa",
    "desenvolve",
    "cria",
    "fecha",
    "atrai",
    "compra",
)
BAD_NAMES = {
    "Brasil",
    "Startup",
    "Startups",
    "IA",
    "AI",
    "SaaS",
    "OpenAI",
    "Nvidia",
    "Google",
    "Microsoft",
}


def clean_html(value: object) -> str:
    text = str(value or "")
    if "<" in text and ">" in text:
        text = BeautifulSoup(text, "html.parser").get_text(" ")
    return re.sub(r"\s+", " ", unescape(text)).strip()


def normalized_text(value: str) -> str:
    return value.casefold()


def has_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = normalized_text(text)
    return any(keyword.casefold() in lowered for keyword in keywords)


def entry_datetime(entry: Any) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        value = getattr(entry, key, None) or entry.get(key)
        if value:
            return datetime(*value[:6], tzinfo=UTC)
    for key in ("published", "updated", "created"):
        value = getattr(entry, key, None) or entry.get(key)
        if not value:
            continue
        try:
            parsed = parsedate_to_datetime(str(value))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except (TypeError, ValueError):
            continue
    return None


def is_recent(entry: Any, *, lookback_days: int) -> bool:
    published_at = entry_datetime(entry)
    if published_at is None:
        return True
    return datetime.now(UTC) - published_at <= timedelta(days=lookback_days)


def _valid_name(value: str) -> bool:
    cleaned = re.sub(r"\s+", " ", value).strip(" -:,.()[]{}")
    if not cleaned or cleaned in BAD_NAMES:
        return False
    if len(cleaned) > 80:
        return False
    words = cleaned.split()
    return 1 <= len(words) <= 4 and any(char.isalpha() for char in cleaned)


def _clean_name(value: str) -> str:
    value = re.sub(rf"^(?:{'|'.join(COMPANY_TRIGGER)})\s+", "", value.strip(), flags=re.I)
    value = re.sub(r"\b(?:brasileira|brasileiro|de|da|do|das|dos|a|o|as|os)\b$", "", value.strip(), flags=re.I)
    value = re.sub(r"\s+", " ", value).strip(" -:,.()[]{}")
    return value


def extract_company_names(title: str, summary: str = "") -> list[str]:
    text = " ".join(part for part in (title, summary) if part)
    candidates: list[str] = []
    capitalized = r"[A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*){0,3}"
    trigger = "|".join(COMPANY_TRIGGER)
    action = "|".join(ACTION_TRIGGER)
    patterns = (
        rf"\b(?:{trigger})\s+({capitalized})",
        rf"\b({capitalized})\s+(?:{action})\b",
        rf"^({capitalized})\s*[,:\-]",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            name = _clean_name(match.group(1))
            if _valid_name(name):
                candidates.append(name)
    seen: set[str] = set()
    deduped: list[str] = []
    for candidate in candidates:
        key = candidate.casefold()
        if key not in seen:
            seen.add(key)
            deduped.append(candidate)
    return deduped


def entry_to_rows(entry: Any, *, feed_url: str, source_name: str, keywords: tuple[str, ...]) -> list[dict[str, Any]]:
    title = clean_html(getattr(entry, "title", None) or entry.get("title"))
    summary = clean_html(getattr(entry, "summary", None) or entry.get("summary") or entry.get("description"))
    link = str(getattr(entry, "link", None) or entry.get("link") or feed_url).strip()
    text = f"{title} {summary}"
    if not title or not has_keyword(text, keywords):
        return []
    names = extract_company_names(title, summary)
    rows: list[dict[str, Any]] = []
    host = (urlsplit(feed_url).hostname or "").removeprefix("www.")
    for name in names:
        identity = f"{name}|{link}|{title}"
        rows.append(
            {
                "startupbase_id": hashlib.sha256(identity.encode("utf-8")).hexdigest(),
                "remote_id": hashlib.sha256(link.encode("utf-8")).hexdigest(),
                "company_name": name,
                "description": f"{title}. {summary}".strip()[:4000],
                "segment": None,
                "stage": None,
                "location": "Brazil" if "brasil" in normalized_text(text) else None,
                "founding_date": None,
                "source_name": source_name if source_name != "RSS News" else f"RSS News: {host}",
                "source_url": link,
                "raw_data": {
                    "feed_url": feed_url,
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "published_at": entry_datetime(entry).isoformat() if entry_datetime(entry) else None,
                },
            }
        )
    return rows
