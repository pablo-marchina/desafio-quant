#!/usr/bin/env python3
"""Automated NVIDIA Corpus Source Sync.

Downloads or updates allowed NVIDIA documentation sources to a staging
area, validates metadata/provenance/hash, generates a sync report, and
optionally promotes to the local corpus.

Usage:
    python scripts/sync_nvidia_sources.py --dry-run
    python scripts/sync_nvidia_sources.py --staging-only
    python scripts/sync_nvidia_sources.py --source-id nim triton --promote
    python scripts/sync_nvidia_sources.py --promote --report-path report.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
import urllib.parse
import urllib.robotparser
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CORPUS_DIR = _PROJECT_ROOT / "data" / "nvidia_corpus"
_ALLOWLIST_FILE = _CORPUS_DIR / "source_allowlist.yaml"
_SOURCES_FILE = _CORPUS_DIR / "sources.yaml"
_STAGING_DIR = _CORPUS_DIR / "staging"
_ARCHIVE_DIR = _CORPUS_DIR / "archive"
_REPORTS_DIR = _CORPUS_DIR / "sync_reports"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_USER_AGENT = "NVIDIA-Startup-AI-Radar/1.0" " (sync; academic-project; contact@example.com)"
_DEFAULT_TIMEOUT = 30
_MAX_DOCUMENT_BYTES = 5_000_000
_DEFAULT_RATE_LIMIT = 2.0

# ---------------------------------------------------------------------------
# Report schema
# ---------------------------------------------------------------------------


@dataclass
class SyncReport:
    sync_run_id: str = ""
    started_at: str = ""
    finished_at: str = ""
    sources_seen: int = 0
    sources_downloaded: int = 0
    sources_unchanged: int = 0
    sources_changed: int = 0
    sources_new: int = 0
    sources_failed: list[str] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)
    promoted_files: list[str] = field(default_factory=list)
    skipped_files: list[str] = field(default_factory=list)
    hashes: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    allowlist_version: str = ""


# ---------------------------------------------------------------------------
# Allowlist loading & validation
# ---------------------------------------------------------------------------


def load_allowlist() -> dict[str, Any]:
    """Load and validate source_allowlist.yaml. Returns dict of source_id -> source."""
    if not _ALLOWLIST_FILE.exists():
        print(f"  ERROR: Allowlist not found: {_ALLOWLIST_FILE}", file=sys.stderr)
        sys.exit(1)
    raw = yaml.safe_load(_ALLOWLIST_FILE.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "sources" not in raw:
        print("  ERROR: Allowlist must contain a 'sources' list", file=sys.stderr)
        sys.exit(1)
    allowlist_version = raw.get("allowlist_version", "unknown")
    sources_list: list[dict[str, Any]] = raw["sources"]
    sources: dict[str, Any] = {}
    for entry in sources_list:
        sid = entry.get("source_id")
        if not sid:
            print("  WARNING: Allowlist entry missing source_id, skipping")
            continue
        sources[sid] = entry
        sources[sid]["_allowlist_version"] = allowlist_version
    return sources


def validate_allowlist_entry(entry: dict[str, Any]) -> list[str]:
    """Validate a single allowlist entry. Returns list of error messages."""
    errors: list[str] = []
    sid = entry.get("source_id", "?")
    if "title" not in entry or not entry["title"]:
        errors.append(f"source '{sid}': title is required")
    url = entry.get("url", "")
    if not url:
        errors.append(f"source '{sid}': url is required")
    elif not url.startswith("https://"):
        errors.append(f"source '{sid}': url must start with https://")
    if "product" not in entry or not entry["product"]:
        errors.append(f"source '{sid}': product is required")
    if "gap_types" not in entry or not isinstance(entry["gap_types"], list):
        errors.append(f"source '{sid}': gap_types must be a list")
    if "document_type" not in entry or not entry["document_type"]:
        errors.append(f"source '{sid}': document_type is required")
    if "version" not in entry or not entry["version"]:
        errors.append(f"source '{sid}': version is required")
    if "freshness_policy" not in entry or not entry["freshness_policy"]:
        errors.append(f"source '{sid}': freshness_policy is required")
    if entry.get("allowed") is True and "stale_after_days" not in entry:
        errors.append(f"source '{sid}': stale_after_days is required")
    if "allowed" not in entry or not isinstance(entry["allowed"], bool):
        errors.append(f"source '{sid}': allowed must be true or false")
    return errors


# ---------------------------------------------------------------------------
# Content hashing
# ---------------------------------------------------------------------------


def compute_content_hash(text: str) -> str:
    """Deterministic MD5 hash of text content."""
    return hashlib.md5(text.encode("utf-8"), usedforsecurity=False).hexdigest()


# ---------------------------------------------------------------------------
# Safe fetcher
# ---------------------------------------------------------------------------


def _http_client() -> httpx.Client:
    """Return a shared httpx client for the sync script."""
    if not hasattr(_http_client, "_client"):
        _http_client._client = httpx.Client(  # type: ignore[attr-defined]
            http2=True,
            timeout=httpx.Timeout(_DEFAULT_TIMEOUT, connect=15.0),
            headers={"User-Agent": _DEFAULT_USER_AGENT},
            follow_redirects=True,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )
    return _http_client._client  # type: ignore[attr-defined]


def fetch_url(
    url: str,
    max_bytes: int = _MAX_DOCUMENT_BYTES,
    timeout: int = _DEFAULT_TIMEOUT,
    user_agent: str = _DEFAULT_USER_AGENT,
) -> tuple[str | None, str | None]:
    """Fetch a URL safely. Returns (content_text, error_message).

    Never follows redirects to external domains. No cookies. No login.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("https",):
        return None, "URL scheme must be https"

    client = _http_client()
    try:
        resp = client.get(url, timeout=timeout)
        resp.raise_for_status()

        # Check content-length
        content_length = resp.headers.get("Content-Length")
        if content_length and int(content_length) > max_bytes:
            return None, f"Content-Length {content_length} exceeds max {max_bytes}"

        raw = resp.content
        if len(raw) > max_bytes:
            return None, f"Response body exceeds max {max_bytes} bytes"

        # Try UTF-8, fallback to charset
        charset = resp.encoding or "utf-8"
        try:
            text = raw.decode(charset)
        except (UnicodeDecodeError, LookupError):
            text = raw.decode("utf-8", errors="replace")

        if len(text.strip()) < 100:
            return None, f"Response too short ({len(text.strip())} chars)"

        return text, None
    except httpx.HTTPStatusError as exc:
        return None, f"HTTP {exc.response.status_code}: {exc.response.reason_phrase}"
    except httpx.TimeoutException:
        return None, f"Timeout after {timeout}s"
    except httpx.ConnectError as exc:
        return None, f"Connection error: {exc}"
    except httpx.RemoteProtocolError as exc:
        return None, f"Protocol error: {exc}"
    except httpx.HTTPError as exc:
        return None, f"HTTP error: {exc}"


def check_robots_txt(url: str, user_agent: str = _DEFAULT_USER_AGENT) -> bool:
    """Check if robots.txt allows fetching the given URL. Returns True if allowed."""
    parsed = urllib.parse.urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    robots_url = f"{base}/robots.txt"
    try:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(user_agent, url)
    except Exception:
        # If robots.txt is unreachable, assume allowed (conservative)
        return True


# ---------------------------------------------------------------------------
# Source fetching
# ---------------------------------------------------------------------------


def fetch_source(
    entry: dict[str, Any],
    rate_limit: float,
    max_docs: int,
    already_fetched: int,
) -> dict[str, Any]:
    """Fetch a single allowed source. Returns result dict with status/hash/content."""
    sid = entry["source_id"]
    url = entry["url"]
    result: dict[str, Any] = {
        "source_id": sid,
        "url": url,
        "status": "skipped",
        "content": None,
        "content_hash": None,
        "error": None,
        "fetch_time": None,
    }

    if not entry.get("allowed", False):
        result["status"] = "disallowed"
        result["error"] = "source not allowed"
        return result

    # Rate limit
    if already_fetched > 0 and rate_limit > 0:
        time.sleep(rate_limit)

    if max_docs is not None and already_fetched >= max_docs:
        result["status"] = "skipped"
        result["error"] = "max-documents limit reached"
        return result

    robots_url = entry.get("url", "")
    if not check_robots_txt(robots_url):
        result["status"] = "failed"
        result["error"] = "disallowed by robots.txt"
        return result

    text, error = fetch_url(url)
    result["fetch_time"] = datetime.now(UTC).isoformat()

    if error:
        result["status"] = "failed"
        result["error"] = error
        return result

    content_hash = compute_content_hash(text)
    result["status"] = "downloaded"
    result["content"] = text
    result["content_hash"] = content_hash
    return result


# ---------------------------------------------------------------------------
# Staging I/O
# ---------------------------------------------------------------------------


def save_to_staging(
    source_id: str,
    content: str,
    fetch_time: str,
    url: str,
    content_hash: str,
    run_id: str,
) -> Path:
    """Save downloaded content to staging directory. Returns staging path."""
    stamp = fetch_time.replace(":", "").replace("-", "").split(".")[0]
    source_staging = _STAGING_DIR / source_id
    source_staging.mkdir(parents=True, exist_ok=True)

    staging_path = source_staging / f"{stamp}.md"
    staging_path.write_text(content, encoding="utf-8")

    # Save metadata alongside
    meta = {
        "source_id": source_id,
        "url": url,
        "fetch_time": fetch_time,
        "content_hash": content_hash,
        "sync_run_id": run_id,
    }
    meta_path = source_staging / f"{stamp}_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    return staging_path


def get_current_corpus_path(source_id: str) -> Path | None:
    """Return path to existing corpus .md file, or None."""
    md_path = _CORPUS_DIR / f"{source_id}.md"
    if md_path.exists():
        return md_path
    return None


def get_current_corpus_hash(source_id: str) -> str | None:
    """Return content hash of existing corpus file, or None."""
    path = get_current_corpus_path(source_id)
    if path is None:
        return None
    text = path.read_text(encoding="utf-8")
    return compute_content_hash(text)


def archive_current(source_id: str, run_timestamp: str) -> Path | None:
    """Archive the current corpus file before promotion. Returns archive path or None."""
    current = get_current_corpus_path(source_id)
    if current is None:
        return None
    archive_dir = _ARCHIVE_DIR / source_id
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_name = f"{run_timestamp}_{source_id}.md"
    archive_path = archive_dir / archive_name
    shutil.copy2(str(current), str(archive_path))
    return archive_path


def promote_to_corpus(
    source_id: str,
    content: str,
    run_timestamp: str,
) -> Path:
    """Promote content to the main corpus directory. Returns corpus path."""
    archive_current(source_id, run_timestamp)
    corpus_path = _CORPUS_DIR / f"{source_id}.md"
    corpus_path.write_text(content, encoding="utf-8")
    return corpus_path


# ---------------------------------------------------------------------------
# Allowlist -> current sources.yaml update
# ---------------------------------------------------------------------------


def update_sources_yaml(
    entry: dict[str, Any],
    allowlist_path: Path = _ALLOWLIST_FILE,
    sources_path: Path = _SOURCES_FILE,
    content_hash: str | None = None,
    checked_at: str | None = None,
) -> bool:
    """Update sources.yaml with metadata from allowlist if changed. Returns True if updated."""
    if not sources_path.exists():
        return False
    raw = yaml.safe_load(sources_path.read_text(encoding="utf-8"))
    sources_dict: dict[str, Any] = raw.get("sources", {})
    sid = entry["source_id"]
    current = sources_dict.get(sid)
    checked_at = checked_at or datetime.now(UTC).isoformat()
    if current is None:
        # New source
        version = entry.get("version", "1.0")
        lifecycle = _build_active_lifecycle(
            version=version,
            content_hash=content_hash,
            previous_content_hash=None,
            checked_at=checked_at,
            entry=entry,
        )
        sources_dict[sid] = {
            "title": entry.get("title", ""),
            "url": entry.get("url", ""),
            "product": entry.get("product", ""),
            "gap_types": entry.get("gap_types", []),
            "document_type": entry.get("document_type", "nvidia_corpus"),
            **lifecycle,
            "versions": [lifecycle],
        }
    else:
        # Update metadata from allowlist
        current["title"] = entry.get("title", current.get("title", ""))
        current["url"] = entry.get("url", current.get("url", ""))
        current["product"] = entry.get("product", current.get("product", ""))
        current["gap_types"] = entry.get("gap_types", current.get("gap_types", []))
        current["document_type"] = entry.get("document_type", current.get("document_type", "nvidia_corpus"))
        current["freshness_policy"] = entry.get(
            "freshness_policy", current.get("freshness_policy", entry.get("update_frequency"))
        )
        current["stale_after_days"] = entry.get("stale_after_days", current.get("stale_after_days"))

        versions = current.get("versions")
        if not isinstance(versions, list) or not versions:
            versions = [_lifecycle_from_top_level(current)]

        active = _find_active_version(versions)
        active_hash = active.get("content_hash") if active else current.get("content_hash")
        if content_hash and active_hash and content_hash != active_hash:
            previous_version = str(active.get("version", current.get("version", "1.0"))) if active else "1.0"
            new_version = _next_version(previous_version)
            if active is not None:
                active["is_active"] = False
                active["deprecated_at"] = checked_at
                active["superseded_by"] = new_version
                active["deprecation_reason"] = "superseded_by_new_content_hash"
            lifecycle = _build_active_lifecycle(
                version=new_version,
                content_hash=content_hash,
                previous_content_hash=active_hash,
                checked_at=checked_at,
                entry=entry,
            )
            versions.append(lifecycle)
            _copy_lifecycle_to_top_level(current, lifecycle)
        else:
            if active is None:
                active = _build_active_lifecycle(
                    version=entry.get("version", current.get("version", "1.0")),
                    content_hash=content_hash or current.get("content_hash"),
                    previous_content_hash=current.get("previous_content_hash"),
                    checked_at=checked_at,
                    entry=entry,
                )
                versions.append(active)
            active["last_checked_at"] = checked_at
            if content_hash:
                active["content_hash"] = content_hash
            _copy_lifecycle_to_top_level(current, active)

        current["versions"] = versions
    raw["sources"] = sources_dict
    sources_path.write_text(
        yaml.safe_dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return True


def _build_active_lifecycle(
    *,
    version: str,
    content_hash: str | None,
    previous_content_hash: str | None,
    checked_at: str,
    entry: dict[str, Any],
) -> dict[str, Any]:
    return {
        "version": version,
        "content_hash": content_hash,
        "previous_content_hash": previous_content_hash,
        "collected_at": checked_at,
        "last_checked_at": checked_at,
        "valid_from": checked_at,
        "valid_until": None,
        "freshness_policy": entry.get("freshness_policy", entry.get("update_frequency")),
        "stale_after_days": entry.get("stale_after_days"),
        "is_active": True,
        "deprecated_at": None,
        "superseded_by": None,
        "deprecation_reason": None,
    }


def _lifecycle_from_top_level(current: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": current.get("version", "1.0"),
        "content_hash": current.get("content_hash"),
        "previous_content_hash": current.get("previous_content_hash"),
        "collected_at": current.get("collected_at"),
        "last_checked_at": current.get("last_checked_at"),
        "valid_from": current.get("valid_from"),
        "valid_until": current.get("valid_until"),
        "freshness_policy": current.get("freshness_policy"),
        "stale_after_days": current.get("stale_after_days"),
        "is_active": current.get("is_active", True),
        "deprecated_at": current.get("deprecated_at"),
        "superseded_by": current.get("superseded_by"),
        "deprecation_reason": current.get("deprecation_reason"),
    }


def _find_active_version(versions: list[dict[str, Any]]) -> dict[str, Any] | None:
    active_versions = [v for v in versions if v.get("is_active") is True]
    return active_versions[-1] if active_versions else None


def _copy_lifecycle_to_top_level(current: dict[str, Any], lifecycle: dict[str, Any]) -> None:
    for field_name, value in lifecycle.items():
        current[field_name] = value


def _next_version(version: str) -> str:
    parts = version.split(".")
    if parts and all(part.isdigit() for part in parts):
        parts[-1] = str(int(parts[-1]) + 1)
        return ".".join(parts)
    return f"{version}+{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"


# ---------------------------------------------------------------------------
# Main sync
# ---------------------------------------------------------------------------


def run_sync(args: argparse.Namespace) -> SyncReport:
    """Run the full source sync pipeline and return a report."""
    run_id = f"sync_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
    started_at = datetime.now(UTC).isoformat()
    report = SyncReport(
        sync_run_id=run_id,
        started_at=started_at,
    )

    # 1. Load allowlist
    print("Step 1/5: Loading allowlist...")
    all_sources = load_allowlist()
    report.allowlist_version = all_sources.get("_allowlist", {}).get("allowlist_version", "1.0")
    print(f"  Allowlist version: {all_sources.get('_allowlist_version', 'unknown')}")
    print(f"  Found {len(all_sources)} source(s) in allowlist")

    # 2. Validate allowlist & filter
    print("Step 2/5: Validating allowlist entries...")
    valid_entries: list[dict[str, Any]] = []
    for sid, entry in all_sources.items():
        errors = validate_allowlist_entry(entry)
        if errors:
            report.validation_errors.extend(f"{sid}: {e}" for e in errors)
            print(f"  VALIDATION ERROR: {sid}: {errors[0]}")
            if args.fail_on_validation_error:
                for err in errors:
                    print(f"  VALIDATION ERROR: {err}", file=sys.stderr)
                sys.exit(1)
        else:
            valid_entries.append(entry)

    if not valid_entries:
        print("  No valid entries. Nothing to sync.")
        report.finished_at = datetime.now(UTC).isoformat()
        return report

    # Filter by source-id
    if args.source_id:
        valid_entries = [e for e in valid_entries if e["source_id"] in args.source_id]
        print(f"  Filtered by source_id: {args.source_id}")

    # Filter by product
    if args.product:
        valid_entries = [
            e for e in valid_entries if any(p.lower() in e.get("product", "").lower() for p in args.product)
        ]
        print(f"  Filtered by product: {args.product}")

    report.sources_seen = len(valid_entries)
    print(f"  {len(valid_entries)} source(s) to process")

    # 3. Fetch sources
    print("Step 3/5: Fetching sources...")
    if args.dry_run:
        print("  DRY RUN — no fetching performed")
        report.finished_at = datetime.now(UTC).isoformat()
        return report

    rate_limit = args.rate_limit_seconds
    max_docs = args.max_documents
    fetch_results: list[dict[str, Any]] = []
    for idx, entry in enumerate(valid_entries):
        sid = entry["source_id"]
        if not entry.get("allowed", False):
            print(f"  SKIPPED {sid} (not allowed)")
            report.skipped_files.append(sid)
            if sid not in report.sources_failed:
                pass
            continue

        print(f"  Fetching {sid}...")
        result = fetch_source(
            entry,
            rate_limit=rate_limit,
            max_docs=max_docs,
            already_fetched=idx,
        )
        fetch_results.append(result)

        if result["status"] == "downloaded":
            report.sources_downloaded += 1
            report.hashes[sid] = result["content_hash"]

            # Save to staging
            staging_path = save_to_staging(
                source_id=sid,
                content=result["content"],
                fetch_time=result["fetch_time"],
                url=result["url"],
                content_hash=result["content_hash"],
                run_id=run_id,
            )
            print(f"    Saved to staging: {staging_path}")

            # Compare with current corpus
            current_hash = get_current_corpus_hash(sid)
            if current_hash is None:
                report.sources_new += 1
                print("    New source (no existing corpus file)")
            elif current_hash == result["content_hash"]:
                report.sources_unchanged += 1
                print("    Unchanged (hash matches existing corpus)")
            else:
                report.sources_changed += 1
                print("    Changed (hash differs from existing corpus)")

        elif result["status"] == "disallowed":
            print("    Skipped (not allowed)")
            report.skipped_files.append(sid)
        elif result["status"] == "failed":
            report.sources_failed.append(sid)
            print(f"    FAILED: {result['error']}")
        elif result["status"] == "skipped":
            print(f"    Skipped: {result['error']}")

    # 4. Promote (only if --promote)
    print("Step 4/5: Promotion...")
    if args.promote:
        run_timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        promoted = 0
        for result in fetch_results:
            if result["status"] != "downloaded":
                continue
            sid = result["source_id"]
            # Check if content actually changed
            current_hash = get_current_corpus_hash(sid)
            if current_hash == result["content_hash"]:
                print(f"  Skipping promote for {sid} (unchanged)")
                update_sources_yaml(
                    next(e for e in valid_entries if e["source_id"] == sid),
                    content_hash=result["content_hash"],
                    checked_at=result["fetch_time"],
                )
                continue
            content = result["content"]
            if content is None:
                continue
            promote_path = promote_to_corpus(sid, content, run_timestamp)
            update_sources_yaml(
                next(e for e in valid_entries if e["source_id"] == sid),
                content_hash=result["content_hash"],
                checked_at=result["fetch_time"],
            )
            report.promoted_files.append(str(promote_path))
            promoted += 1
            print(f"  Promoted {sid} -> {promote_path}")
        if promoted == 0:
            print("  Nothing new to promote")
    else:
        if args.staging_only:
            print("  Staging-only mode — no promotion")
        else:
            print("  No --promote flag — files remain in staging")

    report.finished_at = datetime.now(UTC).isoformat()
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync NVIDIA corpus sources from allowlist.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate allowlist only, no fetching or promotion",
    )
    parser.add_argument(
        "--source-id",
        nargs="+",
        default=None,
        help="Only sync specific source IDs (e.g. nim triton)",
    )
    parser.add_argument(
        "--product",
        nargs="+",
        default=None,
        help="Only sync specific product names",
    )
    parser.add_argument(
        "--promote",
        action="store_true",
        help="Promote validated staging files to corpus",
    )
    parser.add_argument(
        "--staging-only",
        action="store_true",
        help="Download to staging but do not promote",
    )
    parser.add_argument(
        "--report-path",
        type=str,
        default=None,
        help="Save sync report to this path (JSON)",
    )
    parser.add_argument(
        "--fail-on-validation-error",
        action="store_true",
        help="Exit with code 1 if allowlist validation fails",
    )
    parser.add_argument(
        "--max-documents",
        type=int,
        default=None,
        help="Limit number of documents to fetch (for testing)",
    )
    parser.add_argument(
        "--rate-limit-seconds",
        type=float,
        default=_DEFAULT_RATE_LIMIT,
        help=f"Seconds between requests (default: {_DEFAULT_RATE_LIMIT})",
    )
    return parser.parse_args(argv)


def print_report(report: SyncReport) -> None:
    """Print a human-readable sync report."""
    print()
    print("=" * 60)
    print("SYNC REPORT")
    print("=" * 60)
    print(f"  Run ID:               {report.sync_run_id}")
    print(f"  Started:              {report.started_at}")
    print(f"  Finished:             {report.finished_at}")
    print(f"  Sources seen:         {report.sources_seen}")
    print(f"  Sources downloaded:   {report.sources_downloaded}")
    print(f"  Sources unchanged:    {report.sources_unchanged}")
    print(f"  Sources changed:      {report.sources_changed}")
    print(f"  Sources new:          {report.sources_new}")
    print(f"  Sources failed:       {report.sources_failed or 'none'}")
    print(f"  Promoted files:       {len(report.promoted_files)}")
    for pf in report.promoted_files[:5]:
        print(f"    - {pf}")
    if len(report.promoted_files) > 5:
        print(f"    ... and {len(report.promoted_files) - 5} more")
    print(f"  Validation errors:    {len(report.validation_errors)}")
    for err in report.validation_errors[:5]:
        print(f"    - {err}")
    if len(report.validation_errors) > 5:
        print(f"    ... and {len(report.validation_errors) - 5} more")
    if report.hashes:
        print(f"  Content hashes:       {len(report.hashes)} source(s)")
    if report.warnings:
        print(f"  Warnings:             {len(report.warnings)}")
        for w in report.warnings[:5]:
            print(f"    - {w}")
    print("=" * 60)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    print("NVIDIA Corpus Source Sync")
    print(f"  Allowlist: {_ALLOWLIST_FILE}")
    print(f"  Staging:   {_STAGING_DIR}")
    if args.dry_run:
        print("  Mode: DRY RUN (validation only)")
    if args.promote:
        print("  Mode: WITH PROMOTION")
    print()

    report = run_sync(args)
    print_report(report)

    if args.report_path:
        report_path = Path(args.report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(asdict(report), indent=2, default=str),
            encoding="utf-8",
        )
        print(f"Report saved to: {report_path}")

    if report.validation_errors and args.fail_on_validation_error:
        sys.exit(1)


if __name__ == "__main__":
    main()
