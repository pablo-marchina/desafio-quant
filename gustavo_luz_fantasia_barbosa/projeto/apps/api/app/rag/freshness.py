from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable

import requests

from app.scraping import LinkHTMLParser, normalize_text, response_text


Fetcher = Callable[[str, int], dict[str, Any]]

USEFUL_TOPICS: dict[str, tuple[str, ...]] = {
    "model_deployment": (
        "deployment",
        "deploy",
        "inference",
        "serving",
        "production",
        "endpoint",
        "microservice",
    ),
    "inference_latency": (
        "latency",
        "throughput",
        "performance",
        "optimization",
        "tensorrt",
        "triton",
        "nim",
    ),
    "cost_efficiency": (
        "cost",
        "efficient",
        "gpu utilization",
        "batching",
        "scaling",
    ),
    "governance_safety": (
        "governance",
        "guardrail",
        "security",
        "safety",
        "compliance",
        "observability",
        "evaluation",
    ),
    "startup_enablement": (
        "startup",
        "inception",
        "developer",
        "blueprint",
        "catalog",
        "container",
        "sdk",
    ),
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def content_hash(text: str) -> str:
    normalized = " ".join(text.split()).strip().encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def parse_http_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def extract_meta_date(html: str) -> str | None:
    patterns = (
        r'"(?:dateModified|datePublished)"\s*:\s*"([^"]+)"',
        r'<meta[^>]+(?:property|name)=["\'](?:article:modified_time|date|dateModified|datePublished)["\'][^>]+content=["\']([^"\']+)["\']',
        r'<time[^>]+datetime=["\']([^"\']+)["\']',
    )
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def fetch_source_text(url: str, max_chars: int = 12000) -> dict[str, Any]:
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
        "status_code": response.status_code,
        "headers": dict(response.headers),
        "html": html,
        "text": text[:max_chars],
        "characters": len(text),
    }


def classify_startup_usefulness(text: str) -> dict[str, Any]:
    normalized = normalize_text(text)
    matched_topics = []
    score = 0
    for topic, keywords in USEFUL_TOPICS.items():
        hits = sum(1 for keyword in keywords if keyword in normalized)
        if hits:
            matched_topics.append(topic)
            score += min(20, hits * 8)

    usefulness_score = min(100, score)
    return {
        "is_useful_for_startups": usefulness_score >= 24,
        "usefulness_score": usefulness_score,
        "useful_topics": matched_topics,
        "usefulness_reason": (
            "Conteudo menciona temas aplicaveis a startups: "
            + ", ".join(matched_topics)
            if matched_topics
            else "Nao foram encontrados sinais fortes de deployment, performance, governanca ou enablement para startups."
        ),
    }


def freshness_status(
    remote_hash: str,
    remote_modified_at: str | None,
    local_snapshot: dict[str, Any] | None,
) -> str:
    if not local_snapshot:
        return "new"
    if local_snapshot.get("content_hash") == remote_hash:
        return "up_to_date"
    local_modified_at = local_snapshot.get("modified_at")
    if remote_modified_at and local_modified_at and str(remote_modified_at) > str(local_modified_at):
        return "outdated"
    return "changed"


def check_nvidia_source(
    document: dict[str, str],
    *,
    local_snapshot: dict[str, Any] | None = None,
    max_chars: int = 12000,
    fetcher: Fetcher = fetch_source_text,
) -> dict[str, Any]:
    checked_at = utc_now_iso()
    source_url = document["source_url"]

    try:
        fetched = fetcher(source_url, max_chars)
        text = str(fetched.get("text") or "")
        headers = fetched.get("headers") or {}
        html = str(fetched.get("html") or "")
        remote_hash = content_hash(text)
        remote_modified_at = parse_http_date(headers.get("Last-Modified")) or extract_meta_date(html)
        status = freshness_status(remote_hash, remote_modified_at, local_snapshot)
        usefulness = classify_startup_usefulness(
            " ".join(
                [
                    document.get("product_name", ""),
                    document.get("category", ""),
                    document.get("summary", ""),
                    text,
                ]
            )
        )
        action = "none"
        if status in {"new", "changed", "outdated"}:
            action = "ingest_candidate" if usefulness["is_useful_for_startups"] else "manual_review_required"

        return {
            "product_name": document["product_name"],
            "category": document["category"],
            "source_url": fetched.get("source_url") or source_url,
            "checked_at": checked_at,
            "status": status,
            "action": action,
            "local_content_hash": local_snapshot.get("content_hash") if local_snapshot else None,
            "remote_content_hash": remote_hash,
            "local_modified_at": local_snapshot.get("modified_at") if local_snapshot else None,
            "remote_modified_at": remote_modified_at,
            "characters": int(fetched.get("characters") or len(text)),
            "error": None,
            **usefulness,
        }
    except Exception as error:
        return {
            "product_name": document["product_name"],
            "category": document["category"],
            "source_url": source_url,
            "checked_at": checked_at,
            "status": "failed_to_check",
            "action": "none",
            "local_content_hash": local_snapshot.get("content_hash") if local_snapshot else None,
            "remote_content_hash": None,
            "local_modified_at": local_snapshot.get("modified_at") if local_snapshot else None,
            "remote_modified_at": None,
            "characters": 0,
            "is_useful_for_startups": False,
            "usefulness_score": 0,
            "useful_topics": [],
            "usefulness_reason": "Falha ao coletar a fonte remota.",
            "error": str(error),
        }


def check_nvidia_sources(
    documents: list[dict[str, str]],
    *,
    local_snapshots: dict[str, dict[str, Any]] | None = None,
    max_chars: int = 12000,
    fetcher: Fetcher = fetch_source_text,
) -> list[dict[str, Any]]:
    snapshots = local_snapshots or {}
    return [
        check_nvidia_source(
            document,
            local_snapshot=snapshots.get(document["source_url"]),
            max_chars=max_chars,
            fetcher=fetcher,
        )
        for document in documents
    ]
