"""Health check executor — runs real dependency checks for readiness service.

Each check maps to a ``health_check_key`` defined on a ``CapabilityDefinition``.
Results are cached with a TTL to avoid hammering dependencies on every request.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.services.product.capability_registry import CapabilityStatus


@dataclass
class HealthCheckResult:
    status: CapabilityStatus
    latency_ms: float = 0.0
    detail: str = ""


_executor: HealthCheckExecutor | None = None


def get_health_executor() -> HealthCheckExecutor:
    global _executor
    if _executor is None:
        _executor = HealthCheckExecutor()
    return _executor


class HealthCheckExecutor:
    """Run cached, real dependency checks by ``health_check_key``."""

    def __init__(self, cache_ttl: float = 30.0) -> None:
        self._cache_ttl = cache_ttl
        self._cache: dict[str, tuple[HealthCheckResult, float]] = {}

    def check(self, key: str) -> HealthCheckResult:
        now = time.monotonic()
        if key in self._cache:
            result, cached_at = self._cache[key]
            if now - cached_at < self._cache_ttl:
                return result
        result = self._execute(key)
        self._cache[key] = (result, now)
        return result

    def invalidate(self, key: str | None = None) -> None:
        if key:
            self._cache.pop(key, None)
        else:
            self._cache.clear()

    def _execute(self, key: str) -> HealthCheckResult:
        start = time.monotonic()
        if key == "product_db":
            result = self._check_product_db()
        elif key == "qdrant":
            result = self._check_qdrant()
        elif key == "rag":
            result = self._check_rag_corpus()
        elif key == "triton":
            result = self._check_triton()
        elif key == "llm_judge":
            result = self._check_llm_judge()
        else:
            result = HealthCheckResult(
                status=CapabilityStatus.unavailable,
                detail=f"No health check implemented for required key '{key}'",
            )
        result.latency_ms = round((time.monotonic() - start) * 1000, 1)
        return result

    def _check_product_db(self) -> HealthCheckResult:
        try:
            from src.database.session import check_product_database

            ok, error = check_product_database()
            if ok:
                return HealthCheckResult(
                    status=CapabilityStatus.available,
                    detail="Database responded to SELECT 1",
                )
            return HealthCheckResult(
                status=CapabilityStatus.unavailable,
                detail=f"Database unreachable: {error}",
            )
        except Exception as exc:
            return HealthCheckResult(
                status=CapabilityStatus.unavailable,
                detail=f"Database health check error: {exc}",
            )

    def _check_qdrant(self) -> HealthCheckResult:
        url = os.environ.get("QDRANT_URL", "")
        if not url:
            return HealthCheckResult(
                status=CapabilityStatus.unavailable,
                detail="QDRANT_URL is not set",
            )
        api_key = os.environ.get("QDRANT_API_KEY") or None
        collection = os.environ.get("QDRANT_COLLECTION", "")
        if not collection:
            return HealthCheckResult(
                status=CapabilityStatus.unavailable,
                detail="QDRANT_COLLECTION is not set",
            )
        min_points = int(os.environ.get("QDRANT_MIN_POINTS", "10"))
        try:
            from qdrant_client import QdrantClient

            client = QdrantClient(url=url, api_key=api_key, timeout=5)
            collections = client.get_collections().collections
            existing = {c.name for c in collections}
            if collection not in existing:
                return HealthCheckResult(
                    status=CapabilityStatus.degraded,
                    detail=f"Qdrant reachable but collection '{collection}' not found",
                )
            count = client.count(collection_name=collection).count
            if count == 0:
                return HealthCheckResult(
                    status=CapabilityStatus.degraded,
                    detail=f"Qdrant collection '{collection}' exists but is empty",
                )
            if count < min_points:
                return HealthCheckResult(
                    status=CapabilityStatus.degraded,
                    detail=(
                        f"Qdrant collection '{collection}' has only {count} point(s), "
                        f"below minimum threshold of {min_points}"
                    ),
                )
            return HealthCheckResult(
                status=CapabilityStatus.available,
                detail=f"Qdrant reachable at {url}, collection '{collection}' has {count} point(s)",
            )
        except ImportError:
            return HealthCheckResult(
                status=CapabilityStatus.unavailable,
                detail="qdrant-client package not installed",
            )
        except Exception as exc:
            return HealthCheckResult(
                status=CapabilityStatus.unavailable,
                detail=f"Qdrant unreachable at {url}: {exc}",
            )

    def _check_triton(self) -> HealthCheckResult:
        health_url = os.environ.get("TRITON_RERANKER_HEALTH_URL", "").strip()
        if not health_url:
            infer_url = os.environ.get("TRITON_RERANKER_URL", "").strip()
            if infer_url.endswith("/infer"):
                health_url = infer_url[: -len("/infer")] + "/ready"
        if not health_url:
            return HealthCheckResult(
                status=CapabilityStatus.unavailable,
                detail="TRITON_RERANKER_HEALTH_URL is not configured",
            )
        try:
            import httpx

            response = httpx.get(health_url, timeout=5.0)
            if response.status_code == 200:
                return HealthCheckResult(
                    status=CapabilityStatus.available,
                    detail=f"Triton cross_encoder model is ready at {health_url}",
                )
            return HealthCheckResult(
                status=CapabilityStatus.unavailable,
                detail=f"Triton readiness returned HTTP {response.status_code} at {health_url}",
            )
        except Exception as exc:
            return HealthCheckResult(
                status=CapabilityStatus.unavailable,
                detail=f"Triton reranker unavailable at {health_url}: {exc}",
            )

    def _check_rag_corpus(self) -> HealthCheckResult:
        corpus_dir = Path("data/nvidia_corpus")
        if not corpus_dir.exists():
            return HealthCheckResult(
                status=CapabilityStatus.unavailable,
                detail="Corpus directory 'data/nvidia_corpus' not found",
            )
        md_files = sorted(corpus_dir.glob("*.md"))
        md_files = [f for f in md_files if f.name != "README.md"]
        if not md_files:
            return HealthCheckResult(
                status=CapabilityStatus.degraded,
                detail="Corpus directory exists but no markdown documents found",
            )
        sources_file = corpus_dir / "sources.yaml"
        if not sources_file.exists():
            return HealthCheckResult(
                status=CapabilityStatus.degraded,
                detail="Corpus files found but sources.yaml is missing",
            )
        manifest_path = corpus_dir / ".ingestion_manifest.json"
        manifest_ok, manifest_detail = _validate_ingestion_manifest(corpus_dir)
        if manifest_path.exists() and not manifest_ok:
            return HealthCheckResult(
                status=CapabilityStatus.degraded,
                detail=manifest_detail,
            )
        freshness_error = _check_sources_freshness(sources_file)
        if freshness_error and not manifest_ok:
            return HealthCheckResult(
                status=CapabilityStatus.degraded,
                detail=freshness_error,
            )
        detail = manifest_detail if manifest_ok else f"Corpus found with {len(md_files)} document(s)"
        if freshness_error and manifest_ok:
            detail = f"{detail}; upstream review warning: {freshness_error}"
        return HealthCheckResult(
            status=CapabilityStatus.available,
            detail=detail,
        )

    def _check_llm_judge(self) -> HealthCheckResult:
        enabled = os.environ.get("ANSWER_QUALITY_LLM_JUDGE_ENABLED", "false").lower()
        if enabled != "true":
            return HealthCheckResult(
                status=CapabilityStatus.unavailable,
                detail="ANSWER_QUALITY_LLM_JUDGE_ENABLED is not set to true",
            )
        provider = os.environ.get("ANSWER_QUALITY_LLM_JUDGE_PROVIDER", "")
        legacy_provider = os.environ.get("LLM_PROVIDER", "")
        if not provider and legacy_provider:
            provider = legacy_provider
        if not provider:
            return HealthCheckResult(
                status=CapabilityStatus.degraded,
                detail="LLM judge enabled but ANSWER_QUALITY_LLM_JUDGE_PROVIDER env var is not set",
            )
        if provider == "null":
            return HealthCheckResult(
                status=CapabilityStatus.degraded,
                detail=(
                    "ANSWER_QUALITY_LLM_JUDGE_PROVIDER=null uses the offline "
                    "NullLLMJudgeProvider and is not a semantic quality judge"
                ),
            )
        return HealthCheckResult(
            status=CapabilityStatus.degraded,
            detail=f"ANSWER_QUALITY_LLM_JUDGE_PROVIDER={provider} has no active runtime provider implementation",
        )



def _validate_ingestion_manifest(corpus_dir: Path) -> tuple[bool, str]:
    """Validate that the active Qdrant index was built from current corpus bytes.

    Source review freshness and index freshness are deliberately separate. A
    recently built, hash-matched index is operationally usable even when the
    upstream documentation review policy is overdue; that overdue review is
    surfaced as an explicit warning by ``_check_rag_corpus``.
    """
    manifest_path = corpus_dir / ".ingestion_manifest.json"
    if not manifest_path.exists():
        return False, "Corpus ingestion manifest is missing"
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"Corpus ingestion manifest is unreadable: {exc}"

    expected_collection = os.environ.get("QDRANT_COLLECTION", "").strip()
    manifest_collection = str(payload.get("collection_name") or "").strip()
    if expected_collection and manifest_collection != expected_collection:
        return False, (
            f"Corpus ingestion manifest targets collection '{manifest_collection}', "
            f"expected '{expected_collection}'"
        )
    if str(payload.get("backend") or "").casefold() != "qdrant":
        return False, "Corpus ingestion manifest was not produced for Qdrant"

    finished_at = payload.get("finished_at")
    if not finished_at:
        return False, "Corpus ingestion manifest has no finished_at timestamp"
    try:
        finished = datetime.fromisoformat(str(finished_at).replace("Z", "+00:00"))
        max_age_hours = float(os.environ.get("RAG_INDEX_MAX_AGE_HOURS", "168"))
    except (TypeError, ValueError) as exc:
        return False, f"Corpus ingestion manifest has invalid freshness metadata: {exc}"
    age_hours = max(0.0, (datetime.now(UTC) - finished).total_seconds() / 3600.0)
    if age_hours > max_age_hours:
        return False, (
            f"Corpus index manifest is {age_hours:.1f}h old, above "
            f"RAG_INDEX_MAX_AGE_HOURS={max_age_hours:g}"
        )

    manifest_hashes = payload.get("source_hashes") or {}
    if not isinstance(manifest_hashes, dict) or not manifest_hashes:
        return False, "Corpus ingestion manifest has no source hashes"

    sources_file = corpus_dir / "sources.yaml"
    if not sources_file.exists():
        return False, "Corpus sources.yaml is missing"
    try:
        import yaml

        sources_payload: dict[str, Any] = yaml.safe_load(sources_file.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return False, f"Corpus sources.yaml is unreadable: {exc}"
    governed_sources = sources_payload.get("sources") or {}
    active_ids = {
        str(source_id)
        for source_id, item in governed_sources.items()
        if isinstance(item, dict) and item.get("is_active") is not False
    }
    if not active_ids:
        return False, "Corpus sources.yaml has no active governed sources"
    if set(manifest_hashes) != active_ids:
        missing = sorted(active_ids - set(manifest_hashes))
        extra = sorted(set(manifest_hashes) - active_ids)
        return False, f"Corpus ingestion manifest source set mismatch (missing={missing}, extra={extra})"

    missing_documents = sorted(source_id for source_id in active_ids if not (corpus_dir / f"{source_id}.md").exists())
    if missing_documents:
        return False, f"Active corpus document(s) missing: {', '.join(missing_documents)}"
    mismatched: list[str] = []
    for source_id in sorted(active_ids):
        source_path = corpus_dir / f"{source_id}.md"
        current_hash = hashlib.md5(source_path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
        if str(manifest_hashes.get(source_id)) != current_hash:
            mismatched.append(source_id)
    if mismatched:
        return False, f"Corpus changed after ingestion for source(s): {', '.join(sorted(mismatched))}"

    documents_valid = int(payload.get("documents_valid") or 0)
    chunks_created = int(payload.get("chunks_created") or 0)
    if documents_valid != len(active_ids) or chunks_created <= 0:
        return False, (
            f"Corpus ingestion manifest is incomplete: documents_valid={documents_valid}, "
            f"active_sources={len(active_ids)}, chunks_created={chunks_created}"
        )
    return True, (
        f"hash-matched Qdrant index built {age_hours:.2f}h ago from "
        f"{documents_valid} document(s) and {chunks_created} chunk(s)"
    )


def _check_sources_freshness(sources_file: Path) -> str:
    try:
        import yaml
    except ImportError:
        return "PyYAML is not installed; cannot audit corpus freshness"

    try:
        payload: dict[str, Any] = yaml.safe_load(sources_file.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return f"Failed to read corpus freshness metadata: {exc}"

    now = datetime.now(UTC)
    stale: list[str] = []
    expired: list[str] = []
    for source_id, item in (payload.get("sources") or {}).items():
        if not isinstance(item, dict) or item.get("is_active") is False:
            continue
        valid_until = item.get("valid_until")
        if valid_until:
            try:
                expiry = datetime.fromisoformat(str(valid_until).replace("Z", "+00:00"))
            except ValueError:
                expired.append(str(source_id))
            else:
                if expiry < now:
                    expired.append(str(source_id))
        last_checked = item.get("last_checked_at") or item.get("collected_at")
        stale_after = item.get("stale_after_days")
        if last_checked and stale_after is not None:
            try:
                checked_at = datetime.fromisoformat(str(last_checked).replace("Z", "+00:00"))
                stale_days = int(stale_after)
            except (TypeError, ValueError):
                stale.append(str(source_id))
            else:
                if (now - checked_at).days > stale_days:
                    stale.append(str(source_id))

    if expired:
        return f"Corpus has expired active source(s): {', '.join(sorted(expired))}"
    if stale:
        return f"Corpus has stale active source(s): {', '.join(sorted(stale))}"
    return ""
