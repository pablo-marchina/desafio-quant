from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from pydantic import BaseModel, Field

try:
    import tldextract
except ImportError:
    tldextract = None


class DeduplicatedSource(BaseModel):
    canonical_url: str
    source_ids: list[str] = Field(default_factory=list)
    duplicate_count: int = Field(ge=0)


def canonicalize_source_url(url: str) -> str:
    parsed = urlparse(url.strip())
    raw_host = parsed.netloc.casefold()
    if tldextract is not None:
        ext = tldextract.extract(raw_host)
        # Reconstruct: domain.suffix (drop subdomain for canonical)
        host = f"{ext.domain}.{ext.suffix}"
    else:
        host = raw_host
        if host.startswith("www."):
            host = host[4:]
    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=False)
            if not key.casefold().startswith("utm_")
        ]
    )
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((parsed.scheme.casefold() or "https", host, path, "", query, ""))


def deduplicate_sources(sources: dict[str, str]) -> list[DeduplicatedSource]:
    grouped: dict[str, list[str]] = {}
    for source_id, url in sources.items():
        grouped.setdefault(canonicalize_source_url(url), []).append(source_id)
    return [
        DeduplicatedSource(
            canonical_url=url,
            source_ids=sorted(source_ids),
            duplicate_count=max(0, len(source_ids) - 1),
        )
        for url, source_ids in sorted(grouped.items())
    ]
