#!/usr/bin/env python3
"""Refresh NVIDIA corpus freshness without replacing curated documents.

The historical sync command can promote downloaded HTML. This release command
instead verifies every stale active source against its official URL, validates
that the curated local document still matches its recorded hash, and only then
updates ``last_checked_at`` atomically.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import httpx
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CORPUS_DIR = PROJECT_ROOT / "data" / "nvidia_corpus"
OFFICIAL_HOST_SUFFIXES = (
    "nvidia.com",
    "nvidia.github.io",
    "rapids.ai",
)


@dataclass
class SourceRefreshResult:
    source_id: str
    status: str
    url: str
    final_url: str = ""
    http_status: int | None = None
    latency_ms: float = 0.0
    detail: str = ""


@dataclass
class CorpusRefreshReport:
    generated_at: str
    checked: int = 0
    refreshed: int = 0
    fresh_skipped: int = 0
    failures: list[SourceRefreshResult] = field(default_factory=list)
    results: list[SourceRefreshResult] = field(default_factory=list)


def _parse_timestamp(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _is_stale(source: dict[str, object], now: datetime) -> bool:
    stale_after = source.get("stale_after_days")
    if stale_after is None:
        return False
    checked_at = _parse_timestamp(source.get("last_checked_at") or source.get("collected_at"))
    if checked_at is None:
        return True
    return now - checked_at >= timedelta(days=int(stale_after))


def _hash_file(path: Path) -> str:
    return hashlib.md5(path.read_text(encoding="utf-8").encode("utf-8"), usedforsecurity=False).hexdigest()


def _official_https_url(url: str) -> bool:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").casefold()
    return parsed.scheme == "https" and any(
        hostname == suffix or hostname.endswith(f".{suffix}") for suffix in OFFICIAL_HOST_SUFFIXES
    )


def _active_version(source: dict[str, object]) -> dict[str, object] | None:
    versions = source.get("versions")
    if not isinstance(versions, list):
        return None
    active = [item for item in versions if isinstance(item, dict) and item.get("is_active") is True]
    return active[-1] if active else None


def _verify_remote(client: httpx.Client, source_id: str, url: str) -> SourceRefreshResult:
    started = datetime.now(UTC)
    try:
        response = client.get(url)
        latency_ms = (datetime.now(UTC) - started).total_seconds() * 1000
        final_url = str(response.url)
        if response.status_code >= 400:
            return SourceRefreshResult(
                source_id=source_id,
                status="failed",
                url=url,
                final_url=final_url,
                http_status=response.status_code,
                latency_ms=round(latency_ms, 1),
                detail=f"official URL returned HTTP {response.status_code}",
            )
        if not _official_https_url(final_url):
            return SourceRefreshResult(
                source_id=source_id,
                status="failed",
                url=url,
                final_url=final_url,
                http_status=response.status_code,
                latency_ms=round(latency_ms, 1),
                detail="redirect left the governed NVIDIA/RAPIDS domains",
            )
        if len(response.content) < 100:
            return SourceRefreshResult(
                source_id=source_id,
                status="failed",
                url=url,
                final_url=final_url,
                http_status=response.status_code,
                latency_ms=round(latency_ms, 1),
                detail="official response was unexpectedly short",
            )
        return SourceRefreshResult(
            source_id=source_id,
            status="verified",
            url=url,
            final_url=final_url,
            http_status=response.status_code,
            latency_ms=round(latency_ms, 1),
            detail="official source reachable; curated document preserved",
        )
    except httpx.HTTPError as exc:
        latency_ms = (datetime.now(UTC) - started).total_seconds() * 1000
        return SourceRefreshResult(
            source_id=source_id,
            status="failed",
            url=url,
            latency_ms=round(latency_ms, 1),
            detail=f"{type(exc).__name__}: {exc}",
        )


def refresh_metadata(
    corpus_dir: Path = DEFAULT_CORPUS_DIR,
    *,
    now: datetime | None = None,
    timeout_seconds: float = 30.0,
) -> CorpusRefreshReport:
    generated_at = (now or datetime.now(UTC)).astimezone(UTC)
    sources_path = corpus_dir / "sources.yaml"
    raw = yaml.safe_load(sources_path.read_text(encoding="utf-8")) or {}
    sources = raw.get("sources") or {}
    if not isinstance(sources, dict):
        raise RuntimeError("sources.yaml must contain a mapping named 'sources'")

    report = CorpusRefreshReport(generated_at=generated_at.isoformat())
    pending_updates: list[tuple[dict[str, object], dict[str, object] | None]] = []
    headers = {
        "User-Agent": "NVIDIA-Startup-AI-Radar/1.0 (+production-corpus-freshness)",
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    }
    with httpx.Client(
        timeout=httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 15.0)),
        follow_redirects=True,
        headers=headers,
        limits=httpx.Limits(max_connections=5, max_keepalive_connections=5),
    ) as client:
        for source_id, value in sorted(sources.items()):
            if not isinstance(value, dict) or value.get("is_active") is not True:
                continue
            if not _is_stale(value, generated_at):
                report.fresh_skipped += 1
                continue

            report.checked += 1
            local_path = corpus_dir / f"{source_id}.md"
            expected_hash = str(value.get("content_hash") or "")
            if not local_path.exists():
                result = SourceRefreshResult(
                    source_id=source_id,
                    status="failed",
                    url=str(value.get("url") or ""),
                    detail=f"curated document missing: {local_path.name}",
                )
            elif not expected_hash or _hash_file(local_path) != expected_hash:
                result = SourceRefreshResult(
                    source_id=source_id,
                    status="failed",
                    url=str(value.get("url") or ""),
                    detail="curated document hash does not match sources.yaml",
                )
            else:
                url = str(value.get("url") or "")
                if not _official_https_url(url):
                    result = SourceRefreshResult(
                        source_id=source_id,
                        status="failed",
                        url=url,
                        detail="source URL is outside governed NVIDIA/RAPIDS domains",
                    )
                else:
                    result = _verify_remote(client, source_id, url)

            report.results.append(result)
            if result.status == "verified":
                pending_updates.append((value, _active_version(value)))
            else:
                report.failures.append(result)

    if report.failures:
        return report

    checked_at = generated_at.isoformat()
    for source, active in pending_updates:
        source["last_checked_at"] = checked_at
        if active is not None:
            active["last_checked_at"] = checked_at
    report.refreshed = len(pending_updates)
    if pending_updates:
        sources_path.write_text(
            yaml.safe_dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely refresh official NVIDIA corpus source metadata.")
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR)
    parser.add_argument("--report-path", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()

    report = refresh_metadata(args.corpus_dir, timeout_seconds=args.timeout_seconds)
    payload = json.dumps(asdict(report), indent=2, ensure_ascii=False)
    if args.report_path:
        args.report_path.parent.mkdir(parents=True, exist_ok=True)
        args.report_path.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 1 if report.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
