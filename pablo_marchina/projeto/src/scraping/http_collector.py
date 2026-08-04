"""Real HTTP collector governed by Source Registry and Decision Calibration.

Only consumes production_enabled=true sources. Respects compliance rules,
robots.txt, rate limits, and calibrated decisions for timeout/retry/backoff.

No mock, no fake, no stub in the productive path.
"""

from __future__ import annotations

import atexit
import hashlib
import logging
import re
import signal
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from statistics import median
from typing import Any
from urllib.parse import urlparse

try:
    from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
except ImportError:  # pragma: no cover - lightweight fallback for clean source tests
    class _RetryPredicate:
        def __or__(self, other):
            return self

    def retry(*args, **kwargs):
        def decorator(fn):
            def wrapper(*w_args, **w_kwargs):
                attempts = 1
                stop_obj = kwargs.get("stop")
                attempts = getattr(stop_obj, "attempts", attempts)
                last_exc = None
                for _ in range(max(1, int(attempts))):
                    try:
                        return fn(*w_args, **w_kwargs)
                    except Exception as exc:
                        last_exc = exc
                if last_exc is not None:
                    raise last_exc
            return wrapper
        return decorator

    def retry_if_exception_type(*args, **kwargs):
        return _RetryPredicate()

    class stop_after_attempt:
        def __init__(self, attempts):
            self.attempts = attempts

    def wait_exponential(*args, **kwargs):
        return None

from pydantic import BaseModel, Field

from src.quality.decision_calibration_registry import (
    get_project_decision_inventory,
    validate_decision_for_production,
)
from src.scraping.cache import scrape_cache
from src.scraping.circuit_breaker import CircuitBreaker
from src.scraping.content_quality import ContentQualityValidator, QualityIssue
from src.scraping.domain_rate_limiter import DomainRateLimiter
from src.scraping.fetcher import fetch_page
from src.scraping.fuzzy_dedup import DedupIndex
from src.scraping.parser import extract_clean_text
from src.scraping.rate_limit_policy import get_rate_limit_policy
from src.scraping.source_registry import SourceRecord, list_production_enabled_sources
from src.scraping.strategies import resolve_and_call as call_strategy

logger = logging.getLogger(__name__)

# Lazy-import the strategy modules up-front to avoid repeated import side-effects
try:
    import src.scraping.youtube_collector  # noqa: F401
    import src.scraping.rss_collector  # noqa: F401
    import src.scraping.pdf_collector  # noqa: F401
    import src.scraping.firecrawl_collector  # noqa: F401
    import src.scraping.playwright_collector  # noqa: F401
except ImportError as exc:
    logger.warning("Strategy module import failed (some collectors disabled): %s", exc)

_HTTP_COLLECTOR_USER_AGENT = (
    "Mozilla/5.0 (compatible; NVIDIAStartupAIRadar-HttpCollector/0.1; +https://github.com/nvidia/startup-ai-radar)"
)

# Collector types that should be routed through the strategy registry instead of HTTP.
_STRATEGY_HANDLED_TYPES: frozenset[str] = frozenset({
    "youtube", "rss", "pdf", "firecrawl", "playwright", "optional_playwright",
})

# Robots.txt cache: netloc -> (RobotsChecker, timestamp)
_robots_cache: dict[str, tuple["RobotsChecker", float]] = {}
_robots_cache_lock = threading.Lock()
_ROBOTS_CACHE_TTL = 86400  # 24 hours

# Max parallel workers for concurrent fetching
MAX_PARALLEL_WORKERS = 5

# ── Calibration Decision IDs ─────────────────────────────────────────────

DECISION_HTTP_TIMEOUT = "collection.http_timeout_seconds"
DECISION_HTTP_MAX_RETRIES = "collection.http_max_retries"
DECISION_HTTP_BACKOFF_BASE = "collection.http_backoff_base_seconds"

_CALIBRATION_DECISIONS: list[tuple[str, str]] = [
    (DECISION_HTTP_TIMEOUT, "timeout_seconds"),
    (DECISION_HTTP_MAX_RETRIES, "max_retries"),
    (DECISION_HTTP_BACKOFF_BASE, "backoff_base_seconds"),
]

# ── Pydantic Models ──────────────────────────────────────────────────────


class ComplianceResult(BaseModel):
    passed: bool
    blockers: list[str] = Field(default_factory=list)
    robots_allowed: bool = True
    robots_checked: bool = False


class SourceFetchResult(BaseModel):
    source_id: str
    source_url: str
    status: str = "pending"
    http_status_code: int | None = None
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    content_hash: str | None = None
    raw_html: str = ""
    raw_text: str = ""
    extracted_text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    error_message_sanitized: str | None = None
    compliance_status: str | None = None
    robots_allowed: bool = True
    latency_ms: int = 0
    content_bytes: int = 0
    extraction_status: str = "not_configured"


class CollectionMetrics(BaseModel):
    attempted_sources_count: int = 0
    fetched_sources_count: int = 0
    blocked_sources_count: int = 0
    failed_sources_count: int = 0
    robots_blocked_count: int = 0
    compliance_blocked_count: int = 0
    duplicate_count: int = 0
    total_latency_ms: int = 0
    median_latency_ms: float = 0.0
    total_content_bytes: int = 0
    extraction_success_rate: float = 0.0
    fetch_success_rate: float = 0.0


class CollectionRequest(BaseModel):
    run_id: str
    source_records: list[SourceRecord]
    calibrated_limits: dict[str, Any] = Field(default_factory=dict)
    user_agent: str | None = None
    dry_run: bool = False

    model_config = {"arbitrary_types_allowed": True}


class CollectionResult(BaseModel):
    run_id: str
    request: CollectionRequest
    sources: list[SourceFetchResult] = Field(default_factory=list)
    metrics: CollectionMetrics = Field(default_factory=CollectionMetrics)
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None


# ── Robots Checker ───────────────────────────────────────────────────────


class RobotsChecker:
    """Simple robots.txt parser supporting User-agent, Disallow, Allow, Crawl-delay.

    Longest-matching-path wins (most specific rule). Allow overrides
    Disallow at equal path length. Supports ``*`` wildcard in path.
    """

    _Rule = tuple[re.Pattern[str], int, bool]  # (regex, raw_path_len, is_allow)

    def __init__(self, robots_txt: str = "", user_agent: str = "*") -> None:
        self._rules: list[RobotsChecker._Rule] = []
        self._crawl_delay: float = 0.0
        self._parsed: bool = False
        if robots_txt:
            self._parse(robots_txt, user_agent)

    def _parse(self, robots_txt: str, user_agent: str) -> None:
        self._parsed = True
        current_agents: list[str] = []
        for line in robots_txt.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            lower = line.lower()
            if lower.startswith("user-agent:"):
                agent = line.split(":", 1)[1].strip()
                current_agents = [agent]
            elif lower.startswith("disallow:"):
                path = self._extract_path(line)
                if self._matches_agent(current_agents, user_agent):
                    self._rules.append((self._path_to_regex(path), len(path), False))
            elif lower.startswith("allow:"):
                path = self._extract_path(line)
                if self._matches_agent(current_agents, user_agent):
                    self._rules.append((self._path_to_regex(path), len(path), True))
            elif lower.startswith("crawl-delay:"):
                if self._matches_agent(current_agents, user_agent):
                    try:
                        self._crawl_delay = float(line.split(":", 1)[1].strip())
                    except ValueError:
                        pass

    @staticmethod
    def _extract_path(line: str) -> str:
        parts = line.split(":", 1)
        return parts[1].strip() if len(parts) > 1 else ""

    @staticmethod
    def _path_to_regex(path: str) -> re.Pattern[str]:
        escaped = re.escape(path)
        wildcard_replaced = escaped.replace(r"\*", ".*")
        return re.compile(f"^{wildcard_replaced}")

    @staticmethod
    def _matches_agent(current_agents: list[str], target: str) -> bool:
        return any(a == "*" or a.lower() == target.lower() for a in current_agents)

    def is_allowed(self, url: str) -> bool:
        path = urlparse(url).path or "/"
        if not self._parsed:
            return True
        best_len = -1
        best_is_allow = True
        for pattern, raw_len, is_allow in self._rules:
            if pattern.search(path):
                if raw_len > best_len:
                    best_len = raw_len
                    best_is_allow = is_allow
                elif raw_len == best_len and is_allow and not best_is_allow:
                    best_is_allow = True
        return best_is_allow

    @property
    def crawl_delay(self) -> float:
        return self._crawl_delay

    @property
    def parsed(self) -> bool:
        return self._parsed


# ── Content Hashing ──────────────────────────────────────────────────────


def _compute_content_hash(raw: str | bytes) -> str:
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


# ── Calibration Lookup ───────────────────────────────────────────────────


def _lookup_calibrated_value(
    decision_id: str,
    inventory: list,
) -> tuple[Any, bool, str]:
    """Look up a decision from Decision Calibration Registry.

    Returns (value, is_blocked, block_reason).
    """
    for rec in inventory:
        if rec.decision_id == decision_id:
            result = validate_decision_for_production(rec)
            if not result.passed:
                return None, True, f"{decision_id}: {'; '.join(result.reasons)}"
            return rec.current_value, False, ""
    return None, True, f"{decision_id}: not registered in Decision Calibration Registry"


def _resolve_calibrated_limits(
    request: CollectionRequest,
) -> tuple[dict[str, Any], list[str]]:
    """Resolve timeout/retry/backoff from request.calibrated_limits or registry.

    Returns (limits_dict, blockers_list).
    """
    limits: dict[str, Any] = {}
    blockers: list[str] = []
    inventory = get_project_decision_inventory()

    for decision_id, key in _CALIBRATION_DECISIONS:
        if key in request.calibrated_limits:
            limits[key] = request.calibrated_limits[key]
        else:
            value, blocked, reason = _lookup_calibrated_value(decision_id, inventory)
            if blocked:
                blockers.append(reason)
            else:
                limits[key] = value

    return limits, blockers


# ── Source Compliance ────────────────────────────────────────────────────


def _validate_source(source: SourceRecord) -> ComplianceResult:
    """Run compliance checks against a source record.

    Mirrors SourceRegistry's _apply_production_blockers but as a
    collector-level gate.
    """
    blockers: list[str] = []

    if not source.production_enabled:
        blockers.append("source_not_production_enabled")
    if source.requires_login:
        blockers.append("source_requires_login")
    if source.paywall_risk == "mandatory":
        blockers.append("source_paywall_mandatory")
    if source.calibrated_priority_score is None:
        blockers.append("source_priority_uncalibrated")
    policy = get_rate_limit_policy(source.rate_limit_policy_id)
    if policy is None:
        blockers.append("rate_limit_policy_not_found")

    passed = len(blockers) == 0
    # When robots_required is False, we consider robots "allowed" by default
    robots_allowed = True if not source.robots_required else source.robots_required
    return ComplianceResult(passed=passed, blockers=blockers, robots_allowed=robots_allowed)


# ── HTTP Source Collector ────────────────────────────────────────────────


class HttpSourceCollector:
    """Real HTTP collector governed by Source Registry and Decision Calibration.

    Only collects from production_enabled sources. Each source is validated
    for compliance, robots.txt, rate limits, and calibrated timeout/retry/backoff.
    """

    def __init__(self, user_agent: str | None = None) -> None:
        self._user_agent = user_agent or _HTTP_COLLECTOR_USER_AGENT
        self._dedup_index = DedupIndex()
        self._domain_limiter = DomainRateLimiter()
        self._circuit_breaker = CircuitBreaker()
        self._quality_validator = ContentQualityValidator()

    def collect_one(
        self,
        source: SourceRecord,
        *,
        timeout_s: float = 15,
        max_retries: int = 3,
        backoff_base: float = 2.0,
        dry_run: bool = False,
        policy_limiters: dict[str, float] | None = None,
    ) -> SourceFetchResult:
        """Convenience: collect a single SourceRecord.

        Returns a single SourceFetchResult without building a CollectionRequest.
        """
        return self._collect_one(
            source=source,
            timeout_s=timeout_s,
            max_retries=max_retries,
            backoff_base=backoff_base,
            dry_run=dry_run,
            policy_limiters=policy_limiters or {},
        )

    def collect(self, request: CollectionRequest) -> CollectionResult:
        started_at = datetime.now(UTC)
        self._dedup_index.clear()

        result = CollectionResult(run_id=request.run_id, request=request, started_at=started_at)

        limits, blockers = _resolve_calibrated_limits(request)

        if blockers and not request.dry_run:
            for source in request.source_records:
                result.sources.append(
                    SourceFetchResult(
                        source_id=source.source_id,
                        source_url=source.base_url,
                        status="blocked",
                        compliance_status="calibration_blocked",
                        error_code="calibration_blocked",
                        error_message_sanitized="; ".join(blockers),
                    )
                )
            result.metrics = self._compute_metrics(result.sources)
            result.finished_at = datetime.now(UTC)
            return result

        timeout_s = float(limits.get("timeout_seconds", 15))
        max_retries = int(limits.get("max_retries", 3))
        backoff_base = float(limits.get("backoff_base_seconds", 2.0))

        policy_limiters: dict[str, float] = {}

        source_results: dict[int, SourceFetchResult] = {}
        with ThreadPoolExecutor(max_workers=MAX_PARALLEL_WORKERS) as pool:
            future_map: dict[Any, int] = {}
            for idx, source in enumerate(request.source_records):
                if _is_shutdown():
                    source_results[idx] = SourceFetchResult(
                        source_id=source.source_id,
                        source_url=source.base_url or "",
                        status="skipped",
                        error_code="shutdown",
                        error_message_sanitized="Collection interrupted by shutdown",
                    )
                    continue
                future = pool.submit(
                    self._collect_one,
                    source=source,
                    timeout_s=timeout_s,
                    max_retries=max_retries,
                    backoff_base=backoff_base,
                    dry_run=request.dry_run,
                    policy_limiters=policy_limiters,
                )
                future_map[future] = idx

            for future in as_completed(future_map):
                idx = future_map[future]
                try:
                    source_results[idx] = future.result()
                except Exception as exc:
                    src = request.source_records[idx]
                    source_results[idx] = SourceFetchResult(
                        source_id=src.source_id,
                        source_url=src.base_url or "",
                        status="failed",
                        error_code="parallel_execution_error",
                        error_message_sanitized=str(exc),
                    )

            # Cancel remaining futures on shutdown
            if _is_shutdown():
                for future in future_map:
                    future.cancel()

        result.sources = [source_results.get(i, SourceFetchResult(
            source_id=request.source_records[i].source_id,
            source_url=request.source_records[i].base_url or "",
            status="failed",
            error_code="missing_result",
            error_message_sanitized="Result not collected (likely thread interrupted)",
        )) for i in range(len(request.source_records))]
        result.metrics = self._compute_metrics(result.sources)
        result.finished_at = datetime.now(UTC)
        return result

    def _collect_one(
        self,
        source: SourceRecord,
        timeout_s: float,
        max_retries: int,
        backoff_base: float,
        dry_run: bool,
        policy_limiters: dict[str, float],
    ) -> SourceFetchResult:
        url = (source.base_url or "").strip()
        if not url:
            return SourceFetchResult(
                source_id=source.source_id,
                source_url="",
                status="skipped",
                error_code="no_base_url",
                error_message_sanitized="Source has no base_url configured",
            )

        # 1. Compliance
        compliance = _validate_source(source)
        if not compliance.passed:
            return SourceFetchResult(
                source_id=source.source_id,
                source_url=url,
                status="blocked",
                compliance_status="compliance_blocked",
                error_code="compliance_blocked",
                error_message_sanitized="; ".join(compliance.blockers),
                robots_allowed=compliance.robots_allowed,
            )

        # 2. Robots check — skip if source does not require robots.txt
        if compliance.robots_allowed and source.robots_required:
            robots_checker = self._get_robots_checker(url, timeout_s)
        else:
            robots_checker = RobotsChecker()
        if robots_checker.parsed and not robots_checker.is_allowed(url):
            return SourceFetchResult(
                source_id=source.source_id,
                source_url=url,
                status="blocked",
                compliance_status="robots_blocked",
                error_code="robots_disallowed",
                error_message_sanitized="Disallowed by robots.txt",
                robots_allowed=False,
            )

        # 3. Strategy routing for non-HTTP collector types
        if source.collector_type not in ("http", "") and source.collector_type not in _STRATEGY_HANDLED_TYPES:
            # Before blocking, check if a strategy was registered dynamically for this type
            from src.scraping.strategies import resolve as resolve_strategy_fn
            if resolve_strategy_fn(source) is None:
                return SourceFetchResult(
                    source_id=source.source_id,
                    source_url=url,
                    status="blocked",
                    error_code="unsupported_collector_type",
                    error_message_sanitized=(
                        f"Collector type '{source.collector_type}' has no registered strategy. "
                        f"Expected one of: http, {', '.join(sorted(_STRATEGY_HANDLED_TYPES))}"
                    ),
                )

        if source.collector_type in _STRATEGY_HANDLED_TYPES:
            try:
                strategy_result = call_strategy(source)
            except Exception as exc:
                logger.exception("STRATEGY_ERR  %s  collector_type=%s", source.source_id, source.collector_type)
                return SourceFetchResult(
                    source_id=source.source_id,
                    source_url=url,
                    status="failed",
                    error_code="strategy_error",
                    error_message_sanitized=f"Strategy {source.collector_type} failed: {exc}",
                )
            if strategy_result is None:
                return SourceFetchResult(
                    source_id=source.source_id,
                    source_url=url,
                    status="failed",
                    error_code="strategy_returned_none",
                    error_message_sanitized=f"Strategy {source.collector_type} returned no result",
                )
            full_text = (
                getattr(strategy_result, "full_text", None)
                or getattr(strategy_result, "text", None)
                or getattr(strategy_result, "markdown", None)
                or ""
            )
            raw = (
                getattr(strategy_result, "raw_html", None)
                or getattr(strategy_result, "html", None)
                or getattr(strategy_result, "markdown", None)
                or getattr(strategy_result, "full_text", "")
                or str(strategy_result)
            )
            content_hash = _compute_content_hash(raw)
            extracted_dedup = full_text if full_text else raw
            is_duplicate = self._dedup_index.is_duplicate(extracted_dedup)
            if not is_duplicate:
                self._dedup_index.index(extracted_dedup)
            return SourceFetchResult(
                source_id=source.source_id,
                source_url=url,
                status="duplicate" if is_duplicate else "fetched",
                http_status_code=200,
                fetched_at=getattr(strategy_result, "fetched_at", datetime.now(UTC)),
                content_hash=content_hash,
                raw_html=raw,
                raw_text=raw,
                extracted_text=full_text if full_text else raw,
                metadata={
                    "source_category": source.source_category,
                    "source_name": source.source_name,
                    "source_id": source.source_id,
                    "collector_type": source.collector_type,
                },
                compliance_status="compliant",
                robots_allowed=robots_checker.is_allowed(url),
                latency_ms=0,
                content_bytes=len(raw.encode("utf-8")),
                extraction_status="success" if full_text else "empty",
            )

        # 4. Dry run
        if dry_run:
            return SourceFetchResult(
                source_id=source.source_id,
                source_url=url,
                status="dry_run",
                compliance_status="dry_run",
                robots_allowed=robots_checker.is_allowed(url),
            )

        # 4. Fetch with rate limiting and retry
        policy = get_rate_limit_policy(source.rate_limit_policy_id)
        if policy is None:
            return SourceFetchResult(
                source_id=source.source_id,
                source_url=url,
                status="blocked",
                error_code="rate_limit_policy_not_found",
                error_message_sanitized=(f"Rate limit policy '{source.rate_limit_policy_id}' not found"),
            )

        last_error_msg: str | None = None
        last_http_status: int | None = None
        last_latency: int = 0
        fetched_at = datetime.now(UTC)

        # 5. Check disk cache before hitting the network (with ETag/Last-Modified metadata)
        cached_html: str | None = None
        cached_etag: str | None = None
        cached_last_modified: str | None = None
        with scrape_cache() as cache:
            cached_html, meta = cache.get_with_meta(url)
            cached_etag = meta.get("etag")
            cached_last_modified = meta.get("last_modified")
        if cached_html is not None:
            content_hash = _compute_content_hash(cached_html)
            extracted = None
            extraction_status = "not_configured"
            try:
                extracted_val = extract_clean_text(cached_html)
                if extracted_val.strip():
                    extracted = extracted_val
                    if self._dedup_index.is_duplicate(extracted):
                        extraction_status = "duplicate_skipped"
                    else:
                        self._dedup_index.index(extracted)
                        extraction_status = "success"
                else:
                    extraction_status = "empty"
            except Exception:
                extraction_status = "failed"
            is_duplicate = extraction_status == "duplicate_skipped"
            with scrape_cache() as cache:
                cache.record_hash(url, content_hash)
            return SourceFetchResult(
                source_id=source.source_id,
                source_url=url,
                status="duplicate" if is_duplicate else "fetched",
                http_status_code=200,
                fetched_at=fetched_at,
                content_hash=content_hash,
                raw_html=cached_html,
                raw_text=cached_html,
                extracted_text=extracted,
                metadata={
                    "source_category": source.source_category,
                    "source_name": source.source_name,
                    "source_id": source.source_id,
                    "from_cache": True,
                },
                compliance_status="compliant",
                robots_allowed=robots_checker.is_allowed(url),
                latency_ms=0,
                content_bytes=len(cached_html.encode("utf-8")),
                extraction_status=extraction_status,
            )

        # 5b. Domain-level rate limiter + circuit breaker
        self._domain_limiter.wait_if_needed(url, policy.requests_per_second)
        if self._circuit_breaker.is_open(url):
            self._circuit_breaker.record_failure(url)
            return SourceFetchResult(
                source_id=source.source_id,
                source_url=url,
                status="failed",
                error_code="circuit_open",
                error_message_sanitized="Circuit breaker open for this domain",
            )

        start = time.time()
        fr = self._fetch_with_tenacity(
            url=url,
            timeout_s=timeout_s,
            max_retries=max_retries,
            backoff_base=backoff_base,
            cached_etag=cached_etag,
            cached_last_modified=cached_last_modified,
        )
        elapsed_ms = int((time.time() - start) * 1000)
        last_latency = elapsed_ms
        fetched_at = fr.fetched_at

        if fr.error and fr.status is None:
            # Stale-content fallback: serve cache if all retries failed
            if cached_html is not None:
                logger.warning("Serving stale content for %s (fetch failed: %s)", url, fr.error)
                content_hash = _compute_content_hash(cached_html)
                is_duplicate = self._dedup_index.is_duplicate(cached_html)
                if not is_duplicate:
                    self._dedup_index.index(cached_html)
                with scrape_cache() as cache:
                    cache.record_hash(url, content_hash)
                self._circuit_breaker.record_failure(url)
                return SourceFetchResult(
                    source_id=source.source_id,
                    source_url=url,
                    status="stale",
                    http_status_code=None,
                    fetched_at=fetched_at,
                    content_hash=content_hash,
                    raw_html=cached_html,
                    raw_text=cached_html,
                    extracted_text=None,
                    metadata={"from_cache": True, "stale": True, "stale_reason": fr.error},
                    compliance_status="compliant",
                    robots_allowed=robots_checker.is_allowed(url),
                    latency_ms=elapsed_ms,
                    content_bytes=len(cached_html.encode("utf-8")),
                    extraction_status="stale",
                )
            self._circuit_breaker.record_failure(url)
            return SourceFetchResult(
                source_id=source.source_id,
                source_url=url,
                status="failed",
                http_status_code=None,
                fetched_at=fetched_at,
                error_code="fetch_failed",
                error_message_sanitized=f"Fetch failed after {max_retries} attempt(s): {fr.error}",
                compliance_status="compliant",
                robots_allowed=robots_checker.is_allowed(url),
                latency_ms=last_latency,
                content_bytes=0,
            )

        # Handle 304 Not Modified — serve cached content
        if fr.not_modified and cached_html is not None:
            self._circuit_breaker.record_success(url)
            content_hash = _compute_content_hash(cached_html)
            with scrape_cache() as cache:
                cache.record_hash(url, content_hash)
            extracted = None
            extraction_status = "not_configured"
            try:
                extracted_val = extract_clean_text(cached_html)
                if extracted_val.strip():
                    extracted = extracted_val
                    if self._dedup_index.is_duplicate(extracted):
                        extraction_status = "duplicate_skipped"
                    else:
                        self._dedup_index.index(extracted)
                        extraction_status = "success"
                else:
                    extraction_status = "empty"
            except Exception:
                extraction_status = "failed"
            is_duplicate = extraction_status == "duplicate_skipped"
            return SourceFetchResult(
                source_id=source.source_id,
                source_url=url,
                status="fetched",
                http_status_code=304,
                fetched_at=fetched_at,
                content_hash=content_hash,
                raw_html=cached_html,
                raw_text=cached_html,
                extracted_text=extracted,
                metadata={
                    "source_category": source.source_category,
                    "source_name": source.source_name,
                    "source_id": source.source_id,
                    "from_cache": True,
                    "conditional_hit": True,
                },
                compliance_status="compliant",
                robots_allowed=robots_checker.is_allowed(url),
                latency_ms=elapsed_ms,
                content_bytes=len(cached_html.encode("utf-8")),
                extraction_status=extraction_status,
            )

        # 4xx client errors — circuit breaker but no retry (handled by tenacity already)
        if fr.status is not None and 400 <= fr.status < 500:
            self._circuit_breaker.record_failure(url)
            return SourceFetchResult(
                source_id=source.source_id,
                source_url=url,
                status="failed",
                http_status_code=fr.status,
                fetched_at=fetched_at,
                error_code="http_client_error",
                error_message_sanitized=f"HTTP {fr.status}",
                compliance_status="compliant",
                robots_allowed=robots_checker.is_allowed(url),
                latency_ms=elapsed_ms,
                content_bytes=0,
            )

        # 5xx server errors — all retries exhausted
        if fr.status is not None and fr.status >= 500:
            self._circuit_breaker.record_failure(url)
            return SourceFetchResult(
                source_id=source.source_id,
                source_url=url,
                status="failed",
                http_status_code=fr.status,
                fetched_at=fetched_at,
                error_code="http_server_error",
                error_message_sanitized=f"HTTP {fr.status} (all retries exhausted)",
                compliance_status="compliant",
                robots_allowed=robots_checker.is_allowed(url),
                latency_ms=elapsed_ms,
                content_bytes=0,
            )

        # Success (status < 400)
        if fr.status is not None and fr.status < 400:
            content_hash = _compute_content_hash(fr.raw_html)

            extracted: str | None = None
            extraction_status = "not_configured"
            try:
                extracted_val = extract_clean_text(fr.raw_html)
                if extracted_val.strip():
                    extracted = extracted_val
                    if self._dedup_index.is_duplicate(extracted):
                        extraction_status = "duplicate_skipped"
                    else:
                        self._dedup_index.index(extracted)
                        extraction_status = "success"
                else:
                    extraction_status = "empty"
            except Exception:
                extraction_status = "failed"

            is_duplicate = extraction_status == "duplicate_skipped"

            if not is_duplicate:
                # Validate content quality BEFORE caching
                quality = self._quality_validator.validate(fr.raw_html, url)
                non_minor_issues = [i for i in quality.issues if i != QualityIssue.TOO_SHORT]
                issue_labels = [i.value for i in quality.issues] if non_minor_issues else []

                # Cache the content regardless of quality (avoids re-downloading bad pages)
                with scrape_cache() as cache:
                    cache.set(
                        url,
                        fr.raw_html,
                        policy=source.rate_limit_policy_id,
                        etag=getattr(fr, "etag", None),
                        last_modified=getattr(fr, "last_modified", None),
                    )
                    if not non_minor_issues:
                        cache.record_hash(url, content_hash)

                if non_minor_issues:
                    self._circuit_breaker.record_success(url)
                    return SourceFetchResult(
                        source_id=source.source_id,
                        source_url=url,
                        status="failed",
                        http_status_code=fr.status,
                        fetched_at=fetched_at,
                        content_hash=content_hash,
                        error_code="quality_issue",
                        error_message_sanitized=f"Content quality issues: {', '.join(issue_labels)}",
                        metadata={
                            "source_category": source.source_category,
                            "source_name": source.source_name,
                            "source_id": source.source_id,
                            "quality_issues": issue_labels,
                            "quality_cached": True,
                        },
                        compliance_status="compliant",
                        robots_allowed=robots_checker.is_allowed(url),
                        latency_ms=elapsed_ms,
                        content_bytes=0,
                        extraction_status="blocked_by_quality",
                    )

            self._circuit_breaker.record_success(url)
            return SourceFetchResult(
                source_id=source.source_id,
                source_url=url,
                status="duplicate" if is_duplicate else "fetched",
                http_status_code=fr.status,
                fetched_at=fetched_at,
                content_hash=content_hash,
                raw_html="" if is_duplicate else fr.raw_html,
                raw_text="" if is_duplicate else fr.raw_html,
                extracted_text=extracted,
                metadata={
                    "source_category": source.source_category,
                    "source_name": source.source_name,
                    "source_id": source.source_id,
                },
                compliance_status="compliant",
                robots_allowed=robots_checker.is_allowed(url),
                latency_ms=elapsed_ms,
                content_bytes=len(fr.raw_html.encode("utf-8")) if not is_duplicate else 0,
                extraction_status=extraction_status,
            )

        self._circuit_breaker.record_failure(url)
        return SourceFetchResult(
            source_id=source.source_id,
            source_url=url,
            status="failed",
            http_status_code=fr.status,
            fetched_at=fetched_at,
            error_code="fetch_failed",
            error_message_sanitized=f"Fetch failed after {max_retries} attempt(s): unexpected status",
            compliance_status="compliant",
            robots_allowed=robots_checker.is_allowed(url),
            latency_ms=last_latency,
            content_bytes=0,
        )

    @staticmethod
    def _fetch_with_tenacity(
        url: str,
        timeout_s: float,
        max_retries: int,
        backoff_base: float,
        cached_etag: str | None,
        cached_last_modified: str | None,
    ) -> FetchResult:
        """Single HTTP fetch with tenacity retry for 5xx / 429 / network errors.
        Returns the last FetchResult after exhausting retries.
        """

        class _RetryableServerOrRateLimitError(Exception):
            """Retryable: 429 (rate limit), 5xx, or network errors."""

        class _RetryableNetwork(Exception):
            pass

        @retry(
            stop=stop_after_attempt(max_retries),
            wait=wait_exponential(multiplier=backoff_base, min=1, max=30),
            retry=(retry_if_exception_type(_RetryableServerOrRateLimitError) | retry_if_exception_type(_RetryableNetwork)),
            reraise=True,
        )
        def _do_fetch() -> FetchResult:
            fr = fetch_page(
                url,
                timeout=int(timeout_s),
                if_none_match=cached_etag,
                if_modified_since=cached_last_modified,
            )
            # 304 and success are returned directly
            if fr.not_modified or (fr.status is not None and fr.status < 400):
                return fr
            # 429 (rate limit) — retryable
            if fr.status == 429:
                logger.info("Rate-limited (429) for %s, will retry", url)
                raise _RetryableServerOrRateLimitError(fr)
            # 4xx — not retryable
            if fr.status is not None and 400 <= fr.status < 500:
                return fr
            # 5xx — retryable
            if fr.status is not None and fr.status >= 500:
                logger.debug("Server error %d for %s, will retry", fr.status, url)
                raise _RetryableServerOrRateLimitError(fr)
            # Network error — retryable
            raise _RetryableNetwork(fr.error or "unknown error")

        try:
            return _do_fetch()
        except (_RetryableServerOrRateLimitError, _RetryableNetwork) as exc:
            if hasattr(exc, "args") and exc.args:
                return exc.args[0]
            return FetchResult(
                url=url, status=None, raw_html="", fetched_at=datetime.now(UTC),
                error=f"All {max_retries} retries exhausted",
            )

    def _get_robots_checker(self, base_url: str, timeout: float) -> RobotsChecker:
        """Return cached or freshly-fetched RobotsChecker for *base_url*."""
        global _robots_cache, _robots_cache_lock
        parsed = urlparse(base_url)
        if not parsed.scheme or not parsed.netloc:
            return RobotsChecker()
        netloc = parsed.netloc
        now = time.time()
        with _robots_cache_lock:
            if netloc in _robots_cache:
                checker, ts = _robots_cache[netloc]
                if now - ts < _ROBOTS_CACHE_TTL:
                    return checker
        checker = self._fetch_robots_txt(base_url, timeout)
        with _robots_cache_lock:
            _robots_cache[netloc] = (checker, now)
        return checker

    def _fetch_robots_txt(self, base_url: str, timeout: float) -> RobotsChecker:
        parsed = urlparse(base_url)
        if not parsed.scheme or not parsed.netloc:
            return RobotsChecker()
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        try:
            fr = fetch_page(robots_url, timeout=int(timeout))
            if fr.status == 200 and fr.raw_html:
                return RobotsChecker(fr.raw_html, self._user_agent)
        except Exception as exc:
            logger.warning("Failed to fetch robots.txt from %s: %s", robots_url, exc)
        return RobotsChecker()

    @staticmethod
    def _rate_limit_wait(
        policy_id: str,
        requests_per_second: float,
        policy_limiters: dict[str, float],
    ) -> None:
        interval = 1.0 / max(requests_per_second, 0.5)
        last = policy_limiters.get(policy_id, 0.0)
        now = time.time()
        elapsed = now - last
        if elapsed < interval:
            time.sleep(interval - elapsed)
        policy_limiters[policy_id] = time.time()

    @staticmethod
    def _compute_metrics(sources: list[SourceFetchResult]) -> CollectionMetrics:
        total = len(sources)
        if total == 0:
            return CollectionMetrics()

        fetched = [s for s in sources if s.status == "fetched"]
        blocked = [s for s in sources if s.status == "blocked"]
        failed = [s for s in sources if s.status == "failed"]
        duplicates = [s for s in sources if s.status == "duplicate"]
        robots_blocked = [s for s in sources if s.error_code == "robots_disallowed"]
        compliance_blocked = [s for s in sources if s.error_code == "compliance_blocked"]

        latencies = [s.latency_ms for s in fetched]
        total_latency = sum(latencies)
        median_latency = median(latencies) if latencies else 0.0

        total_content = sum(s.content_bytes for s in fetched)
        extraction_success = sum(1 for s in fetched if s.extraction_status == "success")
        extraction_rate = extraction_success / len(fetched) if fetched else 0.0
        fetch_rate = len(fetched) / total if total else 0.0

        return CollectionMetrics(
            attempted_sources_count=total,
            fetched_sources_count=len(fetched),
            blocked_sources_count=len(blocked),
            failed_sources_count=len(failed),
            robots_blocked_count=len(robots_blocked),
            compliance_blocked_count=len(compliance_blocked),
            duplicate_count=len(duplicates),
            total_latency_ms=total_latency,
            median_latency_ms=median_latency,
            total_content_bytes=total_content,
            extraction_success_rate=extraction_rate,
            fetch_success_rate=fetch_rate,
        )





def list_governed_sources() -> list[SourceRecord]:
    return list_production_enabled_sources()


# ── Graceful Shutdown ──────────────────────────────────────────────────

_shutdown_in_progress = False
_shutdown_lock = threading.Lock()


def _is_shutdown() -> bool:
    with _shutdown_lock:
        return _shutdown_in_progress


def _trigger_shutdown() -> None:
    global _shutdown_in_progress
    with _shutdown_lock:
        _shutdown_in_progress = True
    logger.info("SHUTDOWN triggered — in-flight requests may be interrupted")


def _shutdown_handler(signum: int, frame: object | None = None) -> None:
    _trigger_shutdown()
    logger.warning("Received signal %d, shutting down...", signum)


# Register signal handlers for graceful shutdown
try:
    signal.signal(signal.SIGINT, _shutdown_handler)
    signal.signal(signal.SIGTERM, _shutdown_handler)
except (ValueError, RuntimeError):
    pass  # Not running in main thread, skip signal registration

# Also register atexit to close connections
def _cleanup() -> None:
    from src.scraping.cache import reset_cache
    from src.scraping.fetcher import reset_client
    reset_cache()
    reset_client()
    logger.debug("Cleanup: cache and HTTP client closed")

atexit.register(_cleanup)
