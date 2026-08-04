from __future__ import annotations

import logging
import re
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

RELEVANT_PATHS = [
    "/about",
    "/about-us",
    "/team",
    "/careers",
    "/jobs",
    "/join-us",
    "/blog",
    "/news",
    "/press",
    "/product",
    "/products",
    "/platform",
    "/solutions",
    "/company",
    "/contact",
    "/faq",
    "/customers",
    "/case-studies",
]

SITEMAP_PATHS = ["/sitemap.xml", "/sitemap_index.xml", "/sitemap/"]

_MAX_PAGES = 15
_MAX_CRAWL_DEPTH = 1


def discover_pages(
    startup_url: str,
    *,
    max_pages: int = _MAX_PAGES,
    depth: int = _MAX_CRAWL_DEPTH,
    html: str | None = None,
) -> list[str]:
    """Return a prioritized list of page URLs to scrape for a startup.

    Strategy:
    1. Attempt to parse ``sitemap.xml`` and filter by relevant paths.
    2. If no sitemap (or empty), probe common relevant paths.
    3. If *html* is provided and *depth* > 0, parse homepage for internal links
       and match against relevant path keywords.
    """
    parsed = urlparse(startup_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    discovered: set[str] = set()

    # ── Strategy 1: sitemap.xml ──────────────────────────────────────
    sitemap_urls = _try_sitemap(base)
    for sm_url in sitemap_urls:
        if _is_relevant(sm_url):
            discovered.add(sm_url)
        if len(discovered) >= max_pages:
            return _prioritize(list(discovered), base)

    # ── Strategy 2: common paths ──────────────────────────────────────
    for path in RELEVANT_PATHS:
        full = base + path
        if full not in discovered:
            discovered.add(full)
        if len(discovered) >= max_pages:
            return _prioritize(list(discovered), base)

    # ── Strategy 3: link crawling from homepage HTML ──────────────────
    if html and depth > 0:
        internal_links = _extract_internal_links(html, base)
        for link in internal_links:
            if _is_relevant(link) and link not in discovered:
                discovered.add(link)
            if len(discovered) >= max_pages:
                break

    return _prioritize(list(discovered), base)


def _try_sitemap(base_url: str, http_client: Any | None = None) -> list[str]:
    """Try to fetch and parse sitemap.xml (or sitemap_index.xml).

    Args:
        base_url: Base URL to search for sitemaps.
        http_client: Optional callable ``get(url) -> response`` that respects
            governed scraping policies. Falls back to ``httpx`` if not provided.
    """
    urls: list[str] = []
    for sm_path in SITEMAP_PATHS:
        sm_url = base_url + sm_path
        try:
            if http_client is not None:
                resp = http_client(sm_url)
            else:
                import os
                if os.getenv("APP_MODE", "").casefold() == "product":
                    raise RuntimeError("Direct sitemap discovery is disabled in APP_MODE=product; inject governed http_client.")
                import httpx
                resp = httpx.get(sm_url, timeout=10, follow_redirects=True)
            status = resp.status_code if hasattr(resp, "status_code") else getattr(resp, "status", 0)
            if status != 200:
                continue
            text = resp.text if hasattr(resp, "text") else (resp.content.decode("utf-8") if hasattr(resp, "content") else "")
            # Parse <loc> tags (handles both sitemap.xml and sitemap_index.xml)
            urls.extend(re.findall(r"<loc>\s*(https?://[^<]+)\s*</loc>", text, re.IGNORECASE))
            if urls:
                logger.info("Found %d URLs in sitemap at %s", len(urls), sm_url)
                break
        except Exception as exc:
            logger.debug("Sitemap fetch failed for %s: %s", sm_url, exc)
            continue
    return urls


def _extract_internal_links(html: str, base_url: str) -> list[str]:
    """Extract internal links from HTML that match relevant path patterns."""
    links: set[str] = set()
    for match in re.finditer(r'<a\s+href="([^"]+)"', html, re.IGNORECASE):
        href = match.group(1).strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        full = urljoin(base_url, href)
        # Only keep same-domain links
        if urlparse(full).netloc == urlparse(base_url).netloc:
            links.add(full.split("?")[0].rstrip("/"))
    return list(links)


def _is_relevant(url: str) -> bool:
    """Check if a URL matches one of the relevant content paths."""
    path = urlparse(url).path.lower().rstrip("/")
    if not path:
        return False
    for rp in RELEVANT_PATHS:
        if path == rp or path.startswith(rp + "/"):
            return True
    return False


def _prioritize(urls: list[str], base_url: str) -> list[str]:
    """Sort discovered URLs so the most relevant ones come first."""
    domain = urlparse(base_url).netloc
    scored: list[tuple[int, str]] = []

    for url in urls:
        score = 0
        path = urlparse(url).path.lower()
        # Boost exact match paths
        for i, rp in enumerate(RELEVANT_PATHS):
            if path == rp:
                score += 100 - i * 5
                break
            if path.startswith(rp + "/"):
                score += 50
        # Boost root page
        if not path or path == "/":
            score += 80
        scored.append((score, url))

    scored.sort(key=lambda x: -x[0])
    return [s[1] for s in scored]
