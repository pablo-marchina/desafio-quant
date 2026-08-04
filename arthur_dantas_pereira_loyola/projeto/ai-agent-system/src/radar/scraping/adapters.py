from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from radar.schemas import SearchPlan, SourceCandidate, SourceDocument
from radar.scraping.normalizers import (
    normalize_collected_page_payload,
    normalize_search_result_payloads,
)
from radar.settings import RadarSettings, get_settings


class ExternalProviderDisabledError(RuntimeError):
    """Raised when code tries to use external providers while offline mode is active."""


class ExternalProviderCredentialsError(RuntimeError):
    """Raised when an enabled external provider has no configured credentials."""


class SerpApiSearchAdapter:
    """Adapt a SerpAPI-like response payload into source candidates.

    This class does not call SerpAPI. It only normalizes an already available
    payload, which keeps tests deterministic and avoids handling secrets here.
    """

    provider = "serpapi"

    def __init__(
        self, payload: Mapping[str, Any] | Sequence[Mapping[str, Any]]
    ) -> None:
        self._payload = payload

    def search(self, plan: SearchPlan) -> list[SourceCandidate]:
        results = _extract_search_results(self._payload)
        return normalize_search_result_payloads(results, provider=self.provider)


class PageContentAdapter:
    """Adapt collected page payloads into source documents."""

    def __init__(
        self,
        payloads_by_url: Mapping[str, Mapping[str, Any]],
        *,
        collection_method: str = "fixture_page_content",
    ) -> None:
        self._payloads_by_url = dict(payloads_by_url)
        self._collection_method = collection_method

    def fetch(self, candidate: SourceCandidate) -> SourceDocument:
        url = str(candidate.url)
        payload = self._payloads_by_url.get(url)
        if payload is None:
            raise ValueError(f"No fixture page payload found for URL: {url}")
        return normalize_collected_page_payload(
            payload,
            collection_method=self._collection_method,
            candidate=candidate,
        )


class HtmlPageContentAdapter:
    """Adapt locally available raw HTML into source documents without network calls."""

    def __init__(
        self,
        payloads_by_url: Mapping[str, Mapping[str, Any]],
        *,
        collection_method: str = "offline_html_page",
    ) -> None:
        self._payloads_by_url = dict(payloads_by_url)
        self._collection_method = collection_method

    def fetch(self, candidate: SourceCandidate) -> SourceDocument:
        url = str(candidate.url)
        payload = self._payloads_by_url.get(url)
        if payload is None:
            raise ValueError(f"No raw HTML page payload found for URL: {url}")

        html = _first_payload_text(payload, ("html", "raw_html", "content"))
        if html is None:
            raise ValueError("Raw HTML page payload must include an html field.")

        title, text = _extract_html_text(html)
        return normalize_collected_page_payload(
            {
                "url": url,
                "title": _first_payload_text(payload, ("title", "name", "headline"))
                or title,
                "text": text,
            },
            collection_method=self._collection_method,
            candidate=candidate,
        )


class PlaywrightPageAdapter:
    """Fetch page content via Playwright (Chromium headless) with trafilatura extraction.

    Uses a shared ``PlaywrightPool`` to reuse browser instances across fetches
    and across pipelines, avoiding ~3s launch overhead per page.
    """

    provider = "playwright"

    def __init__(self, settings: RadarSettings | None = None) -> None:
        self._settings = settings or get_settings()

    def fetch(self, candidate: SourceCandidate) -> SourceDocument:
        _ensure_external_provider_enabled(self._settings, self.provider)

        import trafilatura

        from radar.scraping.playwright_pool import get_pool

        pool = get_pool()
        url = str(candidate.url)

        browser = pool.acquire()
        try:
            page = browser.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=self._settings.provider_timeout_seconds * 1000)
                html = page.content()
            finally:
                page.close()
        finally:
            pool.release(browser)

        text = trafilatura.extract(html, include_comments=False, include_tables=True, output_format="txt") or ""
        if not text:
            _, text = _extract_html_text(html)

        title = candidate.title or ""
        payload = {
            "url": url,
            "title": title,
            "text": text,
            "source_type": str(candidate.source_type),
        }
        return normalize_collected_page_payload(
            payload,
            collection_method="playwright_scrape",
            candidate=candidate,
        )


class ConfiguredSerpApiSearchAdapter:
    """Search the web via SerpAPI (Google backend)."""

    provider = "serpapi"

    def __init__(self, settings: RadarSettings | None = None) -> None:
        self._settings = settings or get_settings()

    def search(self, plan: SearchPlan) -> list[SourceCandidate]:
        _ensure_external_provider_enabled(self._settings, self.provider)
        _ensure_api_key(self._settings.serpapi_api_key, self.provider)

        import urllib.request
        import urllib.parse
        import json

        candidates = []
        seen_urls: set[str] = set()
        search_queries = _search_queries_for_plan(plan)
        search_queries = _prioritize_ia_queries(search_queries)
        per_query_limit = max(5, 15 // len(search_queries))

        for search_query in search_queries:
            try:
                params = urllib.parse.urlencode({
                    "q": search_query,
                    "api_key": self._settings.serpapi_api_key,
                    "engine": "google",
                    "num": per_query_limit,
                    "hl": "pt",
                })
                url = f"https://serpapi.com/search?{params}"
                req = urllib.request.Request(url, headers={"User-Agent": "radar/1.0"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode())

                results = data.get("organic_results") or []
                for item in results:
                    link = item.get("link") or item.get("url") or ""
                    if not link or link in seen_urls:
                        continue
                    seen_urls.add(link)
                    candidates.append({
                        "url": link,
                        "title": item.get("title", ""),
                        "description": item.get("snippet", ""),
                        "source_type": _infer_source_type_from_url(link, plan.query, plan.keywords),
                        "rank": len(candidates) + 1,
                    })
            except Exception as exc:
                import traceback
                print(f"[SERPAPI DEBUG] Query '{search_query}' failed: {type(exc).__name__}: {exc}")
                traceback.print_exc()
                continue
            import time
            time.sleep(0.5)
        print(f"[SERPAPI DEBUG] Total candidates: {len(candidates)}")

        return normalize_search_result_payloads(
            [{
                "link": c["url"],
                "title": c["title"],
                "snippet": c["description"],
                "kind": c["source_type"],
                "rank": c["rank"],
            } for c in candidates],
            provider=self.provider,
        )


class FirecrawlSearchAdapter:
    """Search the web via Firecrawl's search API."""

    provider = "firecrawl"

    def __init__(self, settings: RadarSettings | None = None) -> None:
        self._settings = settings or get_settings()

    def search(self, plan: SearchPlan) -> list[SourceCandidate]:
        _ensure_external_provider_enabled(self._settings, self.provider)
        _ensure_api_key(self._settings.firecrawl_api_key, self.provider)

        from firecrawl import Firecrawl

        client = Firecrawl(api_key=self._settings.firecrawl_api_key)

        candidates = []
        seen_urls: set[str] = set()
        search_queries = _search_queries_for_plan(plan)
        search_queries = _prioritize_ia_queries(search_queries)
        per_query_limit = max(5, 15 // len(search_queries))

        for search_query in search_queries:
            response = client.search(query=search_query, limit=per_query_limit)
            for item in (response.web or []):
                url = str(item.url)
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                candidates.append({
                    "url": item.url,
                    "title": item.title or "",
                    "description": item.description or "",
                    "source_type": _infer_source_type_from_url(item.url, plan.query),
                    "rank": len(candidates) + 1,
                })
            for item in (response.news or []):
                url = str(item.url)
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                candidates.append({
                    "url": item.url,
                    "title": item.title or "",
                    "description": item.snippet or "",
                    "source_type": "news",
                    "rank": len(candidates) + 1,
                })

        return normalize_search_result_payloads(
            [{  # normalize_search_result_payload expects specific keys
                "link": c["url"],
                "title": c["title"],
                "snippet": c["description"],
                "kind": c["source_type"],
                "rank": c["rank"],
            } for c in candidates],
            provider=self.provider,
        )


class DuckDuckGoSearchAdapter:
    """Search the web via DuckDuckGo (free, no API key required)."""

    provider = "duckduckgo"

    def search(self, plan: SearchPlan) -> list[SourceCandidate]:
        _ensure_external_provider_enabled(get_settings(), self.provider)

        from ddgs import DDGS

        candidates = []
        seen_urls: set[str] = set()
        search_queries = _search_queries_for_plan(plan)
        search_queries = _prioritize_ia_queries(search_queries)
        per_query_limit = max(5, 15 // len(search_queries))

        for search_query in search_queries:
            try:
                results = DDGS().text(search_query, max_results=per_query_limit)
                import time
                time.sleep(2)
            except Exception:
                continue

            for item in results:
                url = item.get("href") or item.get("link") or ""
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                candidates.append({
                    "url": url,
                    "title": item.get("title", ""),
                    "description": item.get("body", item.get("snippet", "")),
                    "source_type": _infer_source_type_from_url(url, plan.query, plan.keywords),
                    "rank": len(candidates) + 1,
                })

        return normalize_search_result_payloads(
            [{
                "link": c["url"],
                "title": c["title"],
                "snippet": c["description"],
                "kind": c["source_type"],
                "rank": c["rank"],
            } for c in candidates],
            provider=self.provider,
        )


class FirecrawlPageAdapter:
    """Fetch page content via Firecrawl's scrape API."""

    provider = "firecrawl"

    def __init__(self, settings: RadarSettings | None = None) -> None:
        self._settings = settings or get_settings()

    def fetch(self, candidate: SourceCandidate) -> SourceDocument:
        _ensure_external_provider_enabled(self._settings, self.provider)
        _ensure_api_key(self._settings.firecrawl_api_key, self.provider)

        from firecrawl import Firecrawl

        client = Firecrawl(api_key=self._settings.firecrawl_api_key)
        doc = client.scrape_url(
            url=str(candidate.url),
            formats=["markdown", "rawHtml"],
            only_main_content=True,
        )

        text = doc.markdown or ""
        if not text and doc.raw_html:
            _, text = _extract_html_text(doc.raw_html)

        title = (doc.metadata.title if doc.metadata and doc.metadata.title else candidate.title) or ""

        payload = {
            "url": str(candidate.url),
            "title": title,
            "text": text,
            "source_type": str(candidate.source_type),
        }
        return normalize_collected_page_payload(
            payload,
            collection_method="firecrawl_scrape",
            candidate=candidate,
        )


def _first_payload_text(
    payload: Mapping[str, Any], keys: tuple[str, ...]
) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _extract_html_text(html: str) -> tuple[str | None, str]:
    soup = BeautifulSoup(html, "html.parser")
    for noisy_tag in soup(("script", "style", "noscript")):
        noisy_tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else None
    lines = [line.strip() for line in soup.get_text(separator="\n").splitlines()]
    text = "\n".join(line for line in lines if line)
    if not text:
        raise ValueError("Raw HTML page payload must include readable text content.")
    return title, text


def _extract_search_results(
    payload: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    if isinstance(payload, Mapping):
        organic_results = payload.get("organic_results")
        if isinstance(organic_results, list):
            return [result for result in organic_results if isinstance(result, Mapping)]
        return [payload]
    return [result for result in payload if isinstance(result, Mapping)]


def _ensure_external_provider_enabled(settings: RadarSettings, provider: str) -> None:
    if not settings.enable_external_providers:
        raise ExternalProviderDisabledError(
            f"{provider} is disabled. Set RADAR_ENABLE_EXTERNAL_PROVIDERS=true only "
            "after explicit authorization to use external APIs."
        )


def _ensure_api_key(api_key: str | None, provider: str) -> None:
    if not api_key:
        raise ExternalProviderCredentialsError(
            f"{provider} is enabled but no API key was configured."
        )


def _prioritize_ia_queries(queries: list[str]) -> list[str]:
    ia_keywords = (" IA", " inteligência", " artificial", " artificial intelligence", " AI")
    ia_queries = [q for q in queries if any(k in q for k in ia_keywords)]
    other_queries = [q for q in queries if q not in ia_queries]
    return ia_queries + other_queries


def _search_queries_for_plan(plan: SearchPlan, max_queries: int = 3) -> list[str]:
    queries = [plan.query.strip()]
    for keyword in plan.keywords:
        normalized = keyword.strip()
        if normalized and normalized not in queries:
            queries.append(normalized)
        if len(queries) >= max_queries:
            break
    return queries


def _infer_source_type_from_url(url: str, query: str | None = None, extra_terms: list[str] | None = None) -> str:
    url_lower = url.lower()
    parsed = urlparse(url_lower)
    domain = parsed.netloc.removeprefix("www.")
    query_terms = list(_meaningful_query_terms(query))
    if extra_terms:
        for t in extra_terms:
            cleaned = "".join(c for c in t.lower() if c.isalnum())
            if len(cleaned) >= 3 and cleaned not in query_terms:
                query_terms.append(cleaned)

    if any(d in url_lower for d in ("crunchbase", "pitchbook", "startupbase", "distrito")):
        return "startup_directory"
    if any(d in url_lower for d in ("linkedin", "glassdoor")):
        return "careers"
    if any(n in url_lower for n in ("g1.", "globo", "valor", "forbes", "infomoney", "startups")):
        return "news"
    if "nvidia" in url_lower:
        return "nvidia_documentation"
    if any(b in url_lower for b in ("blog.", "/blog", "medium.com")):
        return "blog"
    if any(j in url_lower for j in ("/sobre", "/about", "/quem-somos")):
        return "official_site"
    if query_terms and any(term in domain for term in query_terms):
        return "official_site"
    return "other"


def _meaningful_query_terms(query: str | None) -> list[str]:
    if not query:
        return []
    stopwords = {
        "a",
        "as",
        "com",
        "de",
        "do",
        "da",
        "das",
        "dos",
        "e",
        "em",
        "ia",
        "o",
        "os",
        "para",
        "startup",
        "startups",
    }
    terms = []
    for raw in query.lower().replace("-", " ").replace("_", " ").split():
        term = "".join(char for char in raw if char.isalnum())
        if len(term) >= 3 and term not in stopwords:
            terms.append(term)
    return terms
