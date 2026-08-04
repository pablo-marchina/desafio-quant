"""Evidence scraping node using DuckDuckGo, trafilatura and BeautifulSoup."""

from __future__ import annotations

import re
import time
from html import unescape
from typing import Iterable
from urllib.parse import urlsplit

import httpx
import trafilatura
from trafilatura import settings as trafilatura_settings
from bs4 import BeautifulSoup

try:
    from ddgs import DDGS
except ModuleNotFoundError:  # pragma: no cover - exercised only when dependency is missing.
    DDGS = None

from .. import config
from ..state import EnrichmentState

_last_request_at = 0.0
LOW_VALUE_HOSTS = ("instagram.com", "facebook.com", "x.com", "twitter.com", "youtube.com", "tiktok.com")


def _trafilatura_config():
    tf_config = trafilatura_settings.use_config()
    timeout = str(int(config.HTTP_TIMEOUT_SECONDS))
    tf_config.set("DEFAULT", "download_timeout", timeout)
    tf_config.set("DEFAULT", "extraction_timeout", timeout)
    return tf_config


def _rate_limit() -> None:
    global _last_request_at
    minimum_interval = 1.0 / max(config.REQUESTS_PER_SECOND, 0.01)
    elapsed = time.monotonic() - _last_request_at
    if elapsed < minimum_interval:
        time.sleep(minimum_interval - elapsed)
    _last_request_at = time.monotonic()


def _request_html(url: str) -> str:
    last_error: Exception | None = None
    for attempt in range(config.MAX_RETRIES):
        try:
            _rate_limit()
            with httpx.Client(timeout=config.HTTP_TIMEOUT_SECONDS, follow_redirects=True) as client:
                response = client.get(url, headers={"User-Agent": "Startup AI Radar/1.0"})
                response.raise_for_status()
                return response.text
        except Exception as error:
            last_error = error
            delay = config.BACKOFF_SECONDS[min(attempt, len(config.BACKOFF_SECONDS) - 1)]
            time.sleep(delay)
    raise RuntimeError(last_error or f"falha ao buscar {url}")


def extract_with_trafilatura(html: str, url: str) -> str:
    return (trafilatura.extract(html, url=url, include_comments=False, include_tables=False) or "").strip()


def extract_with_bs4(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = " ".join(soup.stripped_strings)
    return unescape(re.sub(r"\s+", " ", text)).strip()


def extract_text_from_url(url: str) -> str:
    try:
        _rate_limit()
        html = trafilatura.fetch_url(url, config=_trafilatura_config()) or ""
        text = extract_with_trafilatura(html, url) if html else ""
        if _is_useful_text(text):
            return text
    except Exception:
        pass

    html = _request_html(url)
    text = extract_with_bs4(html)
    return text if _is_useful_text(text) else ""


def _candidate_query(candidate: dict[str, object]) -> str:
    return str(candidate.get("company_name") or candidate.get("nome") or "").strip()


def _candidate_urls(candidate: dict[str, object]) -> list[str]:
    urls: list[str] = []
    for key in ("website", "website_url", "site", "source_url", "linkedin_url"):
        value = str(candidate.get(key) or "").strip()
        if value.startswith("http"):
            urls.append(value)
    return urls


def _candidate_description(candidate: dict[str, object]) -> str:
    return str(
        candidate.get("description")
        or candidate.get("descricao")
        or candidate.get("summary")
        or ""
    ).strip()


def _candidate_source(candidate: dict[str, object]) -> str:
    for key in ("source_url", "website", "website_url", "linkedin_url"):
        value = str(candidate.get(key) or "").strip()
        if value:
            return value
    return "candidate:original_description"


def _candidate_fallback_evidence(candidate: dict[str, object]) -> tuple[dict[str, str], list[str]]:
    description = _candidate_description(candidate)
    if not _is_useful_text(description):
        return {}, []
    source = _candidate_source(candidate)
    text = (
        f"Descricao original do candidato {candidate.get('company_name') or candidate.get('nome') or ''}: "
        f"{description}"
    ).strip()
    urls = [source] if source.startswith("http") else []
    return {source: text[:6000]}, urls


def build_search_query(company_name: str) -> str:
    return f"{company_name} Brasil tecnologia inteligencia artificial startup".strip()


def discover_urls(candidate: dict[str, object]) -> list[str]:
    company_name = _candidate_query(candidate)
    if not company_name:
        return []
    if DDGS is None:
        raise RuntimeError("ddgs nao esta instalado")

    _rate_limit()
    query = build_search_query(company_name)
    urls: list[str] = _candidate_urls(candidate)
    with DDGS(timeout=config.HTTP_TIMEOUT_SECONDS) as ddgs:
        for result in ddgs.text(query, max_results=8):
            url = str(result.get("href") or result.get("url") or "").strip()
            if url.startswith("http"):
                urls.append(url)
    return _prioritize_urls(list(dict.fromkeys(urls)))


def _is_useful_text(text: str) -> bool:
    return len(text.strip()) > 200


def _is_low_value_url(url: str) -> bool:
    host = (urlsplit(url).hostname or "").casefold()
    return any(host == domain or host.endswith(f".{domain}") for domain in LOW_VALUE_HOSTS)


def _prioritize_urls(urls: list[str]) -> list[str]:
    strong, regular, low_value = [], [], []
    for url in urls:
        lowered = url.casefold()
        if any(domain in lowered for domain in (*config.STRONG_SOURCE_DOMAINS, *config.NEWS_SOURCE_DOMAINS)):
            strong.append(url)
        elif _is_low_value_url(url):
            low_value.append(url)
        else:
            regular.append(url)
    return [*strong, *regular, *low_value]


def scrape_urls(urls: Iterable[str]) -> tuple[dict[str, str], list[str], list[str]]:
    raw_texts: dict[str, str] = {}
    evidence_urls: list[str] = []
    errors: list[str] = []
    for url in _prioritize_urls(list(urls)):
        try:
            text = extract_text_from_url(url)
            if _is_useful_text(text):
                raw_texts[url] = text[:6000]
                evidence_urls.append(url)
                if len(evidence_urls) >= config.MAX_EVIDENCE_PAGES:
                    break
                continue
            errors.append(f"scraping:{urlsplit(url).hostname or url}: texto insuficiente")
        except Exception as error:
            domain = urlsplit(url).hostname or url
            errors.append(f"scraping:{domain}: {error}")
    return raw_texts, evidence_urls, errors


def _merge_scraping_errors(existing: object, scrape_errors: list[str], found_text: bool) -> object:
    if not scrape_errors and found_text:
        return existing
    messages = list(scrape_errors)
    if not found_text:
        messages.append("scraping: nenhum resultado util encontrado no DuckDuckGo")
    if isinstance(existing, dict):
        merged = {key: list(value) if isinstance(value, list) else value for key, value in existing.items()}
        current = merged.get("scraping", [])
        if not isinstance(current, list):
            current = [str(current)]
        merged["scraping"] = [*current, *messages]
        return merged
    return [*(existing or []), *messages]


def web_scrape_node(state: EnrichmentState) -> dict[str, object]:
    candidate = state.get("candidate", {})
    fallback_texts, fallback_urls = _candidate_fallback_evidence(candidate)
    try:
        urls = discover_urls(candidate)
        raw_texts, evidence_urls, scrape_errors = scrape_urls(urls)
    except Exception as error:
        raw_texts, evidence_urls, scrape_errors = {}, [], [f"scraping: DuckDuckGo: {error}"]
    raw_texts = {**fallback_texts, **raw_texts}
    evidence_urls = list(dict.fromkeys([*fallback_urls, *evidence_urls]))
    found_text = bool(raw_texts)
    return {
        "raw_texts": raw_texts,
        "evidence_urls": list(dict.fromkeys([*state.get("evidence_urls", []), *evidence_urls])),
        "errors": _merge_scraping_errors(state.get("errors", {}), scrape_errors, found_text),
    }
