"""Coleta de dados públicos com proveniência (F1).

Adapters: Tavily (busca), Firecrawl, Playwright (dinâmico), trafilatura, BeautifulSoup, Scrapy.
Respeita robots.txt + rate limiting. Registra url/fetched_at/hash em evidence.

Seeds de fontes do §9 (F0.9): `from packages.scraping import load_sources, allowlist`.
Busca de URLs candidatas (F1.1): `from packages.scraping import search, SearchResult`.
Extração limpa de página (F1.2): `from packages.scraping import scrape, ExtractedPage`.
Renderização de página dinâmica (F1.3): `from packages.scraping import render, RenderedPage`.
Texto principal de blog/notícia (F1.4): `extract_article`, `fetch_article`, `Article`.
Parsing estruturado de HTML simples (F1.5): `parse_html`, `fetch_html`, `extract_links`,
`select_text`, `ParsedPage`, `Link`.
Varredura em escala dos diretórios §9 (F1.6): `crawl`, `collectable_seeds`,
`CrawledPage`, `CrawlPlan`.
Roteador de fetch estático vs dinâmico (F1.7): `route`, `FetchResult`, `ContentKind`.
Compliance robots/rate limit/UA + guarda de quota de free tier (F1.8): `ComplianceGate`,
`RobotsCache`, `RateLimiter`, `QuotaGuard`, `USER_AGENT`, `QuotaExceeded`, `RobotsDisallowed`.
Proveniência (url/fetched_at/hash/snippet → tabela `evidence`, F1.9): `record_evidence`,
`persist_evidence`, `to_evidence`, `content_hash`, `make_snippet`.
Persistência do perfil (upsert company/founder + dedup + escopo BR, F1.10):
`persist_profile`, `upsert_company`, `upsert_founder`, `br_scope`, `ScopeVerdict`,
`normalize_domain`, `normalize_cnpj`.
Taxonomia de sinais AI-native (enviesa a busca + pré-filtra candidatas, F1.11):
`scan`, `prefilter`, `bias_query`, `Signal`, `SignalScan`, `TAXONOMY`, `BIAS_TERMS`.
Guarda LGPD de founder (minimização de dado + base legal, F1.13): `sanitize_founder`,
`scan_sensitive`, `redact`, `FounderResult`, `SensitiveHit`, `FOUNDER_LEGAL_BASIS`.
Política de ToS por fonte (allowlist/denylist, F1.15): `SourcePolicyGate`, `SourceVerdict`,
`ToSProhibited`, `source_allowed`, `source_guard`, `source_verdict`.
"""

from .article import Article
from .article import extract as extract_article
from .article import fetch as fetch_article
from .compliance import (
    USER_AGENT,
    ComplianceError,
    ComplianceGate,
    QuotaExceeded,
    QuotaGuard,
    RateLimiter,
    RobotsCache,
    RobotsDisallowed,
)
from .crawler import CrawledPage, CrawlPlan, collectable_seeds, crawl
from .dynamic import RenderedPage, render
from .firecrawl import ExtractedPage, scrape
from .lgpd import (
    FOUNDER_LEGAL_BASIS,
    FounderResult,
    SensitiveHit,
    redact,
    sanitize_founder,
    scan_sensitive,
)
from .persistence import (
    ScopeVerdict,
    br_scope,
    normalize_cnpj,
    normalize_domain,
    persist_profile,
    upsert_company,
    upsert_founder,
)
from .provenance import (
    content_hash,
    make_snippet,
    persist_evidence,
    record_evidence,
    to_evidence,
)
from .router import ContentKind, FetchResult, extract_rendered, is_insufficient
from .router import fetch as route
from .search import SearchResult, search
from .seeds import Source, allowlist, by_type, denylist, load_sources
from .signals import (
    BIAS_TERMS,
    TAXONOMY,
    Signal,
    SignalScan,
    bias_query,
    prefilter,
    scan,
)
from .soup import Link, ParsedPage, extract_links, select_text
from .soup import extract as parse_html
from .soup import fetch as fetch_html
from .source_policy import SourcePolicyGate, SourceVerdict, ToSProhibited
from .source_policy import allowed as source_allowed
from .source_policy import guard as source_guard
from .source_policy import verdict as source_verdict

__all__ = [
    "Source",
    "load_sources",
    "allowlist",
    "denylist",
    "by_type",
    "search",
    "SearchResult",
    "scrape",
    "ExtractedPage",
    "render",
    "RenderedPage",
    "Article",
    "extract_article",
    "fetch_article",
    "ParsedPage",
    "Link",
    "parse_html",
    "fetch_html",
    "extract_links",
    "select_text",
    "crawl",
    "collectable_seeds",
    "CrawledPage",
    "CrawlPlan",
    "route",
    "FetchResult",
    "ContentKind",
    "extract_rendered",
    "is_insufficient",
    "ComplianceGate",
    "ComplianceError",
    "RobotsCache",
    "RobotsDisallowed",
    "RateLimiter",
    "QuotaGuard",
    "QuotaExceeded",
    "USER_AGENT",
    "record_evidence",
    "persist_evidence",
    "to_evidence",
    "content_hash",
    "make_snippet",
    "persist_profile",
    "upsert_company",
    "upsert_founder",
    "br_scope",
    "ScopeVerdict",
    "normalize_domain",
    "normalize_cnpj",
    "scan",
    "prefilter",
    "bias_query",
    "Signal",
    "SignalScan",
    "TAXONOMY",
    "BIAS_TERMS",
    "sanitize_founder",
    "scan_sensitive",
    "redact",
    "FounderResult",
    "SensitiveHit",
    "FOUNDER_LEGAL_BASIS",
    "SourcePolicyGate",
    "SourceVerdict",
    "ToSProhibited",
    "source_allowed",
    "source_guard",
    "source_verdict",
]
