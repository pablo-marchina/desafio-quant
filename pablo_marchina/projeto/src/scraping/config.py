"""Centralized configuration for the scraping module via Pydantic Settings."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class HTTPSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SCRAPING_HTTP_")

    timeout_seconds: int = 15
    connect_timeout_seconds: float = 10.0
    max_response_bytes: int = 5 * 1024 * 1024
    max_keepalive_connections: int = 5
    max_connections: int = 10
    http2_enabled: bool = True
    follow_redirects: bool = True
    user_agent_fallback: str = (
        "Mozilla/5.0 (compatible; NVIDIAStartupAIRadar/0.1; +https://github.com/nvidia/startup-ai-radar)"
    )
    user_agent_browsers: list[str] = Field(default_factory=lambda: ["chrome", "firefox", "edge"])
    allowed_schemes: set[str] = Field(default_factory=lambda: {"http", "https"})
    allowed_content_types: set[str] = Field(
        default_factory=lambda: {"text/html", "application/json", "text/plain", "application/xml", "+xml"}
    )


class CacheSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SCRAPING_CACHE_")

    directory: str = ".cache/scraping"
    size_limit_bytes: int = 2**30
    eviction_policy: str = "least-recently-used"
    freshness_ttl_daily_seconds: int = 86400
    freshness_ttl_weekly_seconds: int = 604800
    freshness_ttl_monthly_seconds: int = 2592000
    freshness_ttl_static_seconds: int = 31536000
    default_ttl_seconds: int = 86400
    hash_history_max_entries: int = 10
    robots_cache_ttl_seconds: int = 86400

    FRESHNESS_POLICY_MAP: ClassVar[dict[str, str]] = {
        "nvidia_product_docs": "weekly",
        "nvidia_blog": "weekly",
        "nvidia_dev_blog": "weekly",
        "nvidia_tech_blog": "weekly",
        "nvidia_tech_docs": "monthly",
        "official": "monthly",
        "news": "daily",
        "crunchbase_funding": "monthly",
        "linkedin": "weekly",
        "angel_list": "monthly",
        "blog": "weekly",
        "docs": "monthly",
        "rss": "daily",
        "sitemap": "monthly",
        "youtube_channel": "monthly",
    }


class RateLimitSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SCRAPING_RATE_LIMIT_")

    min_rps_floor: float = 0.5
    max_parallel_workers: int = 5


class CircuitBreakerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SCRAPING_CIRCUIT_")

    failure_threshold: int = 5
    recovery_timeout_seconds: int = 300


class ContentQualitySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SCRAPING_QUALITY_")

    min_content_length: int = 200
    login_threshold: int = 3
    paywall_threshold: int = 2
    lang_detect_min_length: int = 100
    lang_detect_truncate: int = 2000
    expected_languages: list[str] = Field(default_factory=lambda: ["pt", "en"])
    boilerplate_patterns: list[str] = Field(
        default_factory=lambda: [
            r"(var\s+|function\s+|document\.|window\.|\.addEventListener)",
            r"(adsbygoogle|google_ad|doubleclick)",
            r"(captcha|recaptcha|cf-turnstile)",
            r"(Access Denied|403 Forbidden|404 Not Found)",
            r"(subscribe to continue|subscription required)",
            r"(cookies? policy|cookie consent)",
            r"(sidebar|footer|header|navigation)",
            r"(comment\s+\d+|leave a reply)",
            r"(related posts|you may also like)",
            r"(share this|tweet this|pin this)",
            r"^(<!DOCTYPE|<!doctype|<html|<head)",
            r"(\.css|\.js|\.json|\.xml)\s*$",
            r"(browser check|checking your browser|just a moment)",
        ]
    )
    login_signals: list[str] = Field(
        default_factory=lambda: [
            "sign in", "log in", "login", "sign up", "register",
            "create account", "email address", "password", "forgot password",
        ]
    )
    paywall_signals: list[str] = Field(
        default_factory=lambda: [
            "subscribe", "subscription", "premium", "paywall",
            "paid article", "metered", "limited articles",
            "unlock this article", "members only",
        ]
    )


class ParserSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SCRAPING_PARSER_")

    readability_min_length: int = 100
    trafilatura_min_length: int = 50


class DiscoverySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SCRAPING_DISCOVERY_")

    max_pages: int = 15
    max_crawl_depth: int = 1
    sitemap_fetch_timeout: int = 10
    relevant_paths: list[str] = Field(
        default_factory=lambda: [
            "/about", "/about-us", "/team", "/careers", "/jobs", "/join-us",
            "/blog", "/news", "/press", "/product", "/products", "/platform",
            "/solutions", "/company", "/contact", "/faq", "/customers",
            "/case-studies",
        ]
    )
    sitemap_paths: list[str] = Field(
        default_factory=lambda: ["/sitemap.xml", "/sitemap_index.xml", "/sitemap/"]
    )
    priority_base_score: int = 100
    priority_path_decrement: int = 5
    priority_root_bonus: int = 80
    priority_partial_match_bonus: int = 50


class DirectorySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SCRAPING_DIRECTORY_")

    query_param_max_pages: int = 20
    infinite_scroll_max_pages: int = 10
    next_link_max_pages: int = 20
    pagination_timeout: int = 10


class GitHubSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SCRAPING_GITHUB_")

    api_base_url: str = "https://api.github.com"
    api_timeout: int = 15
    api_user_agent: str = "NVIDIA-Startup-AI-Radar/1.0"
    api_accept_header: str = "application/vnd.github.v3+json"
    token_env_var: str = "GITHUB_TOKEN"
    max_repos: int = 10
    readme_char_cap: int = 50_000


class FounderSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SCRAPING_FOUNDER_")

    social_context_window: int = 500
    role_context_window: int = 200


class ChangeDetectorSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SCRAPING_CHANGE_")

    diff_context_lines: int = 3
    max_diff_lines: int = 20


class FuzzyDedupSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SCRAPING_DEDUP_")

    threshold: float = 0.85


class SourcePolicySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SCRAPING_POLICY_")

    known_official_hints: list[str] = Field(default_factory=lambda: ["about", "company", "careers", "blog"])
    default_quality_score: float = 0.3


class CollectorSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SCRAPING_COLLECTOR_")

    user_agent: str = (
        "Mozilla/5.0 (compatible; NVIDIAStartupAIRadar-HttpCollector/0.1; +https://github.com/nvidia/startup-ai-radar)"
    )
    strategy_handled_types: frozenset[str] = Field(
        default_factory=lambda: frozenset({"youtube", "rss", "pdf", "firecrawl", "playwright", "optional_playwright"})
    )
    max_parallel_workers: int = 5
    default_timeout: int = 15
    default_max_retries: int = 3
    default_backoff_base: float = 2.0
    decision_http_timeout: str = "collection.http_timeout_seconds"
    decision_http_max_retries: str = "collection.http_max_retries"
    decision_http_backoff_base: str = "collection.http_backoff_base_seconds"
    backoff_min: float = 1.0
    backoff_max: float = 30.0
    min_rps_floor: float = 0.5


class ScrapingConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SCRAPING_", extra="ignore")

    http: HTTPSettings = Field(default_factory=HTTPSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    circuit_breaker: CircuitBreakerSettings = Field(default_factory=CircuitBreakerSettings)
    content_quality: ContentQualitySettings = Field(default_factory=ContentQualitySettings)
    parser: ParserSettings = Field(default_factory=ParserSettings)
    discovery: DiscoverySettings = Field(default_factory=DiscoverySettings)
    directory: DirectorySettings = Field(default_factory=DirectorySettings)
    github: GitHubSettings = Field(default_factory=GitHubSettings)
    founder: FounderSettings = Field(default_factory=FounderSettings)
    change_detector: ChangeDetectorSettings = Field(default_factory=ChangeDetectorSettings)
    fuzzy_dedup: FuzzyDedupSettings = Field(default_factory=FuzzyDedupSettings)
    source_policy: SourcePolicySettings = Field(default_factory=SourcePolicySettings)
    collector: CollectorSettings = Field(default_factory=CollectorSettings)

    data_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent / "data")
    source_records_yaml_path: Path | None = None

    @property
    def default_source_records_yaml(self) -> Path:
        return self.data_dir / "scraping" / "source_records.yaml"


config: ScrapingConfig = ScrapingConfig()
