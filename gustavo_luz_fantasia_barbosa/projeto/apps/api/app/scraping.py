from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any
import unicodedata
from urllib.parse import urldefrag, urljoin, urlparse

import requests


class MainTextHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._in_title = False
        self.parts: list[str] = []
        self.title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "svg", "noscript"}:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "svg", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = " ".join(data.split())
        if len(text) >= 3:
            if self._in_title:
                self.title_parts.append(text)
            self.parts.append(text)

    def text(self) -> str:
        return " ".join(self.parts)

    def title(self) -> str:
        return " ".join(self.title_parts).strip()


class LinkHTMLParser(MainTextHTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        super().handle_starttag(tag, attrs)
        if tag != "a":
            return

        attributes = dict(attrs)
        href = attributes.get("href")
        if href:
            self.links.append(href)


STARTUP_LINK_KEYWORDS = (
    "about",
    "company",
    "product",
    "products",
    "platform",
    "solution",
    "solutions",
    "technology",
    "technologies",
    "ai",
    "machine-learning",
    "customers",
    "case-studies",
    "blog",
    "docs",
    "developers",
    "research",
    "security",
    "pricing",
)


class BrazilianStartupValidationError(ValueError):
    pass


def repair_mojibake(text: str) -> str:
    if "Ã" not in text and "Â" not in text:
        return text
    try:
        repaired = text.encode("latin1").decode("utf-8")
    except UnicodeError:
        return text
    if repaired.count("Ã") + repaired.count("Â") < text.count("Ã") + text.count("Â"):
        return repaired
    return text


def response_text(response: requests.Response) -> str:
    encoding = (response.encoding or "").lower()
    if not encoding or encoding == "iso-8859-1":
        response.encoding = response.apparent_encoding or "utf-8"
    return repair_mojibake(response.text)


def normalize_url(url: str) -> str:
    normalized, _fragment = urldefrag(url)
    return normalized.rstrip("/")


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.lower())
    return "".join(
        character for character in normalized if not unicodedata.combining(character)
    )


def has_brazilian_startup_signal(url: str, text: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    normalized_text = normalize_text(text)

    if host.endswith(".br") or ".com.br" in host:
        return True

    brazil_terms = (
        "brasil",
        "brazil",
        "brasileira",
        "brasileiro",
        "brasileiras",
        "brasileiros",
        "sao paulo",
        "rio de janeiro",
        "belo horizonte",
        "florianopolis",
        "porto alegre",
        "curitiba",
        "recife",
    )
    startup_terms = (
        "startup",
        "scaleup",
        "empresa",
        "tecnologia",
        "inteligencia artificial",
        "machine learning",
        "ia",
        "dados",
        "software",
        "plataforma",
    )

    has_brazil_signal = any(term in normalized_text for term in brazil_terms)
    has_startup_context = any(term in normalized_text for term in startup_terms)
    return has_brazil_signal and has_startup_context


def is_same_site(base_url: str, candidate_url: str) -> bool:
    base = urlparse(base_url)
    candidate = urlparse(candidate_url)
    return candidate.scheme in {"http", "https"} and candidate.netloc == base.netloc


def link_priority(url: str) -> int:
    lower_url = url.lower()
    score = 0
    for index, keyword in enumerate(STARTUP_LINK_KEYWORDS):
        if keyword in lower_url:
            score += len(STARTUP_LINK_KEYWORDS) - index
    return score


def extract_candidate_links(base_url: str, links: list[str], max_links: int) -> list[str]:
    candidates = []
    seen: set[str] = set()

    for href in links:
        if href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        absolute_url = normalize_url(urljoin(base_url, href))
        if absolute_url in seen or not is_same_site(base_url, absolute_url):
            continue
        if any(
            absolute_url.lower().endswith(extension)
            for extension in (".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".zip")
        ):
            continue
        seen.add(absolute_url)
        candidates.append(absolute_url)

    candidates.sort(key=link_priority, reverse=True)
    return candidates[:max_links]


def fetch_github_readme_text(url: str, max_chars: int) -> dict[str, Any] | None:
    parsed = urlparse(url)
    if parsed.netloc.lower() != "github.com":
        return None

    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) < 2:
        return None

    owner, repo = path_parts[0], path_parts[1]
    candidates = [
        f"https://raw.githubusercontent.com/{owner}/{repo}/main/README.md",
        f"https://raw.githubusercontent.com/{owner}/{repo}/master/README.md",
        f"https://raw.githubusercontent.com/{owner}/{repo}/main/README.rst",
        f"https://raw.githubusercontent.com/{owner}/{repo}/master/README.rst",
    ]

    last_error: requests.RequestException | None = None
    for candidate in candidates:
        try:
            response = requests.get(
                candidate,
                timeout=10,
                headers={"User-Agent": "NVIDIA-Startup-AI-Radar/0.1"},
            )
            if response.status_code == 404:
                continue
            response.raise_for_status()
            text = " ".join(response.text.split())
            return {
                "source_url": candidate,
                "title": f"{owner}/{repo} README",
                "status_code": response.status_code,
                "characters": len(text),
                "text": text[:max_chars],
                "collected_at": datetime.now(timezone.utc).isoformat(),
            }
        except requests.RequestException as error:
            last_error = error

    if last_error:
        raise last_error
    return None


def fetch_public_website_text(url: str, max_chars: int = 5000) -> dict[str, Any]:
    github_readme = fetch_github_readme_text(url, max_chars=max_chars)
    if github_readme:
        return github_readme

    response = requests.get(
        url,
        timeout=10,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; NVIDIA-Startup-AI-Radar/0.1; "
                "+https://localhost)"
            )
        },
    )
    response.raise_for_status()

    html = response_text(response)
    parser = LinkHTMLParser()
    parser.feed(html)
    text = parser.text()

    return {
        "source_url": response.url,
        "title": parser.title(),
        "status_code": response.status_code,
        "headers": dict(response.headers),
        "html": html,
        "characters": len(text),
        "text": text[:max_chars],
        "links": extract_candidate_links(response.url, parser.links, max_links=24),
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_public_source_evidence(
    url: str,
    *,
    source_type: str,
    max_chars: int = 4500,
) -> dict[str, Any]:
    fetched = fetch_public_website_text(url, max_chars=max_chars)
    return {
        "source_url": fetched["source_url"],
        "title": fetched.get("title") or "",
        "status_code": fetched.get("status_code"),
        "characters": fetched.get("characters", 0),
        "excerpt": str(fetched.get("text") or "")[:360],
        "text": fetched.get("text") or "",
        "source_type": source_type,
        "collected_at": fetched.get("collected_at"),
    }


def crawl_public_website_text(
    url: str,
    max_pages: int = 5,
    max_chars_per_page: int = 5000,
    max_total_chars: int = 18000,
    require_brazilian_startup: bool = False,
) -> dict[str, Any]:
    first_page = fetch_public_website_text(url, max_chars=max_chars_per_page)
    if require_brazilian_startup and not has_brazilian_startup_signal(
        first_page["source_url"],
        first_page["text"],
    ):
        raise BrazilianStartupValidationError(
            "O site informado nao tem sinais suficientes de startup brasileira."
        )

    pages = [first_page]
    visited = {normalize_url(first_page["source_url"])}

    queue = list(first_page.get("links", []))
    while queue and len(pages) < max_pages:
        next_url = normalize_url(queue.pop(0))
        if next_url in visited:
            continue
        visited.add(next_url)

        try:
            page = fetch_public_website_text(next_url, max_chars=max_chars_per_page)
        except requests.RequestException:
            continue

        if page["characters"] < 120:
            continue

        pages.append(page)
        for link in page.get("links", []):
            normalized_link = normalize_url(link)
            if normalized_link not in visited and normalized_link not in queue:
                queue.append(normalized_link)
        queue.sort(key=link_priority, reverse=True)

    combined_parts = []
    total_chars = 0
    for page in pages:
        page_text = page["text"]
        remaining = max_total_chars - total_chars
        if remaining <= 0:
            break
        combined_parts.append(f"Fonte: {page['source_url']}\n{page_text[:remaining]}")
        total_chars += min(len(page_text), remaining)

    combined_text = "\n\n".join(combined_parts)

    return {
        "source_url": first_page["source_url"],
        "status_code": first_page["status_code"],
        "characters": sum(page["characters"] for page in pages),
        "text": combined_text,
        "pages": [
            {
                "source_url": page["source_url"],
                "title": page.get("title") or "",
                "status_code": page["status_code"],
                "characters": page["characters"],
                "excerpt": page["text"][:360],
                "text": page["text"],
                "source_type": "official_website",
                "collected_at": page.get("collected_at"),
            }
            for page in pages
        ],
    }
