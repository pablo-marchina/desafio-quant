from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from app.collectors.html import extract_main_text, extract_title
from app.collectors.source_types import classify_source_type
from app.models.enums import SourceType


@dataclass(frozen=True)
class UrlCollectionPlan:
    url: str
    source_type: SourceType
    should_fetch: bool


@dataclass(frozen=True)
class CollectedSourceDocument:
    url: str
    source_type: SourceType
    title: str | None
    extracted_text: str | None
    scrape_status: str
    scrape_error: str | None = None


def normalize_public_url(url: str) -> str:
    parsed_url = urlparse(url)
    if not parsed_url.scheme:
        return f"https://{url}"
    return url


def plan_url_collection(url: str, should_fetch: bool = False) -> UrlCollectionPlan:
    normalized_url = normalize_public_url(url)
    return UrlCollectionPlan(
        url=normalized_url,
        source_type=classify_source_type(normalized_url),
        should_fetch=should_fetch,
    )


def collect_url(
    url: str,
    user_agent: str,
    timeout_seconds: float = 15.0,
    client: httpx.Client | None = None,
) -> CollectedSourceDocument:
    plan = plan_url_collection(url, should_fetch=True)
    headers = {"User-Agent": user_agent}

    try:
        response = _get_url(plan.url, headers, timeout_seconds, client)
        response.raise_for_status()
    except httpx.HTTPError as error:
        return CollectedSourceDocument(
            url=plan.url,
            source_type=plan.source_type,
            title=None,
            extracted_text=None,
            scrape_status="failed",
            scrape_error=str(error),
        )

    html = response.text
    return CollectedSourceDocument(
        url=plan.url,
        source_type=plan.source_type,
        title=extract_title(html),
        extracted_text=extract_main_text(html),
        scrape_status="succeeded",
    )


def _get_url(
    url: str,
    headers: dict[str, str],
    timeout_seconds: float,
    client: httpx.Client | None,
) -> httpx.Response:
    if client:
        return client.get(url, headers=headers, timeout=timeout_seconds, follow_redirects=True)

    with httpx.Client() as local_client:
        return local_client.get(
            url,
            headers=headers,
            timeout=timeout_seconds,
            follow_redirects=True,
        )
