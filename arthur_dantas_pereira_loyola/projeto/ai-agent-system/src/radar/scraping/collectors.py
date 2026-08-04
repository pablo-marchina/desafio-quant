from __future__ import annotations

from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Protocol

from radar.schemas import PipelineError, SearchPlan, SourceCandidate, SourceDocument
from radar.scraping.normalizers import normalize_source_payloads

MAX_CANDIDATES = 8

DOMAIN_BLOCKLIST: set[str] = {
    "youtube.com", "youtu.be",
    "amazon.com", "amazon.com.br",
    "kbb.com", "kelleybluebook.com",
    "wikipedia.org", "pt.wikipedia.org",
    "dictionary.com", "merriam-webster.com",
    "urbandictionary.com",
    "pinterest.com", "pinterest.com.br",
    "instagram.com", "facebook.com",
    "twitter.com", "x.com", "tiktok.com",
    "reddit.com",
    "ebay.com", "ebay.com.br",
    "walmart.com", "aliexpress.com",
    "imdb.com",
    "spotify.com",
    "tracxn.com",
    "startups.com",
}

RELEVANT_DOMAIN_PATTERNS = (
    "startup", "crunchbase", "pitchbook", "distrito",
    "linkedin", "glassdoor",
    "forbes", "valor", "globo", "infomoney",
    "blog.",
)

STARTUP_DIRECTORY_DOMAINS = (
    "crunchbase", "pitchbook", "startupbase", "distrito",
    "cubo.network", "acestartups", "endeavor",
    "abstartups", "bossainvest", "liga.ventures",
    "openstartups", "startse", "latitud",
    "wow.ac", "inovativa", "darwinstartups",
)


class WebCollector(ABC):
    @abstractmethod
    def collect(self, plan: SearchPlan) -> list[SourceDocument]:
        """Collect public documents for a search plan."""

class SearchProvider(Protocol):
    def search(self, plan: SearchPlan) -> list[SourceCandidate]:
        """Return candidate URLs for a search plan."""


class PageProvider(Protocol):
    def fetch(self, candidate: SourceCandidate) -> SourceDocument:
        """Return a normalized source document for a candidate URL."""


class SearchBackedCollector(WebCollector):
    """Collector that composes a search adapter with a page-content adapter."""

    def __init__(self, search_provider: SearchProvider, page_provider: PageProvider) -> None:
        self._search_provider = search_provider
        self._page_provider = page_provider

    def collect(self, plan: SearchPlan) -> list[SourceDocument]:
        sources, errors = self.collect_with_errors(plan)
        if errors and not sources:
            raise RuntimeError(errors[0].message)
        return sources

    def collect_with_errors(self, plan: SearchPlan) -> tuple[list[SourceDocument], list[PipelineError]]:
        try:
            candidates = self._search_provider.search(plan)
        except Exception as exc:
            return [], [
                PipelineError(
                    step="scraper.search",
                    message=str(exc),
                    recoverable=True,
                    provider=_provider_name(self._search_provider),
                    error_type=type(exc).__name__,
                )
            ]

        candidates = _filter_relevant_candidates(candidates, plan)
        candidates = candidates[:MAX_CANDIDATES]

        sources: list[SourceDocument] = []
        errors: list[PipelineError] = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_candidate = {
                executor.submit(self._page_provider.fetch, candidate): candidate
                for candidate in candidates
            }
            for future in as_completed(future_to_candidate):
                candidate = future_to_candidate[future]
                try:
                    sources.append(future.result())
                except Exception as exc:
                    errors.append(
                        PipelineError(
                            step="scraper.fetch",
                            message=str(exc),
                            recoverable=True,
                            source_url=str(candidate.url),
                            provider=_provider_name(self._page_provider),
                            error_type=type(exc).__name__,
                        )
                    )
        return sources, errors


def _filter_relevant_candidates(
    candidates: list[SourceCandidate], plan: SearchPlan
) -> list[SourceCandidate]:
    def is_relevant(candidate: SourceCandidate) -> bool:
        domain = candidate.domain.lower().removeprefix("www.")
        if _domain_matches_any(domain, DOMAIN_BLOCKLIST):
            return False

        snippet = (candidate.snippet or "").lower()
        title = (candidate.title or "").lower()
        combined = f"{title} {snippet}"

        if _is_candidate_company_mismatch(domain, combined, plan):
            return False

        has_context_hint = _has_context_hint(combined)
        has_startup_signal = candidate.source_type in {"blog", "careers", "startup_directory", "news"}
        if has_startup_signal:
            return True
        if candidate.source_type == "official_site" and has_context_hint:
            return True

        domain_relevant = any(pattern in domain for pattern in RELEVANT_DOMAIN_PATTERNS) or _domain_matches_any(domain, STARTUP_DIRECTORY_DOMAINS)
        if domain_relevant:
            return True

        startup_hints = ("startup", "empresa", "company", "funding",
                         "série", "series", "seed", "investimento",
                         "founder", "ceo", "lança", "product",
                         "solução", "solution", "plataforma", "platform")
        has_hint = any(h in combined for h in startup_hints)
        if has_hint:
            return True

        ai_hints = ("inteligência artificial", "artificial intelligence",
                    "machine learning", "deep learning",
                    "\"ai\"", " ai ", " ai-", "ai-", "-ai", "/ai")
        has_ai_hint = any(h in combined for h in ai_hints)
        if has_ai_hint:
            return True

        query_terms = _query_terms(plan)
        has_query_match = any(term in domain for term in query_terms)
        if has_query_match:
            return True

        keyword_match = any(
            term in domain or term in combined
            for term in _name_keywords(plan)
        )
        if keyword_match:
            return True

        return False

    return [c for c in candidates if is_relevant(c)]


def _name_keywords(plan: SearchPlan) -> list[str]:
    stopwords = {"ai", "ia", "de", "do", "da", "dos", "das", "e", "em", "o", "os", "a", "as", "para", "com", "que", "startup", "startups", "empresa", "empresas"}
    keywords = []
    for kw in plan.keywords:
        cleaned = "".join(c for c in kw.lower() if c.isalnum())
        if len(cleaned) >= 3 and cleaned not in stopwords and cleaned not in keywords:
            keywords.append(cleaned)
    return keywords


def _domain_matches_any(domain: str, patterns: set[str] | tuple[str, ...]) -> bool:
    return any(domain == pattern or domain.endswith(f".{pattern}") for pattern in patterns)


def _has_context_hint(combined: str) -> bool:
    hints = (
        "startup", "empresa", "company", "funding", "founder", "ceo",
        "produto", "product", "solucao", "solução", "solution",
        "plataforma", "platform", "inteligência artificial", "artificial intelligence",
        "machine learning", "deep learning", " ai ", " ia ", "ai-", "-ai", "/ai",
    )
    return any(hint in combined for hint in hints)


def _is_candidate_company_mismatch(domain: str, combined: str, plan: SearchPlan) -> bool:
    terms = set(_query_terms(plan))
    text = f"{domain} {combined}"
    if "traction" in terms and "tractian" in text:
        return True
    if "tractian" in terms and "traction" in text and "tractian" not in domain:
        return True
    commerce_noise = (
        "heavy duty truck", "truck parts", "auto parts", "car parts",
        "kelley blue book", "used cars", "tires", "walmart", "amazon",
    )
    return any(noise in text for noise in commerce_noise) and not _has_context_hint(combined)


def _query_terms(plan: SearchPlan) -> list[str]:
    stopwords = {"ai", "ia", "brasil", "brazil", "startup", "startups", "empresa", "tecnologia"}
    terms: list[str] = []
    for raw in [plan.query, *plan.keywords]:
        for part in raw.lower().replace("-", " ").replace("_", " ").split():
            term = "".join(char for char in part if char.isalnum())
            if len(term) > 2 and term not in stopwords and term not in terms:
                terms.append(term)
    return terms

def _provider_name(provider: object) -> str:
    return str(getattr(provider, "provider", provider.__class__.__name__))


class StaticSeedCollector(WebCollector):
    """Deterministic collector used until real web adapters are added."""

    def collect(self, plan: SearchPlan) -> list[SourceDocument]:
        query = plan.query or "startup"
        raw_payloads = [
            {
                "url": "https://www.nvidia.com/en-us/startups/",
                "source_type": "nvidia",
                "title": "NVIDIA Inception",
                "content": (
                    f"Seed evidence placeholder for {query}: public startup analysis "
                    "needs traceable sources."
                ),
            }
        ]

        if any(marker in query.lower() for marker in ("validada", "validated", "duas fontes")):
            raw_payloads.extend(_scenario_payloads(query))

        return normalize_source_payloads(raw_payloads, collection_method="static_seed")


def _scenario_payloads(query: str) -> list[dict[str, str]]:
    normalized_query = query.lower()
    if any(marker in normalized_query for marker in ("dados", "data", "tabular", "analytics")):
        return _data_payloads()
    if any(marker in normalized_query for marker in ("voz", "voice", "transcricao", "transcrição", "call center")):
        return _voice_payloads()
    if any(marker in normalized_query for marker in ("saude", "saúde", "health", "healthcare", "medical")):
        return _healthcare_payloads()
    if any(marker in normalized_query for marker in ("robot", "robotica", "robótica", "simulacao", "simulação")):
        return _robotics_payloads()
    if any(marker in normalized_query for marker in ("latencia", "latência", "inferencia", "inferência")):
        return _latency_payloads()
    return _llm_agent_payloads()


def _llm_agent_payloads() -> list[dict[str, str]]:
    return [
        {
            "source_url": "https://example.com/startup-ai-platform",
            "type": "official",
            "name": "Example AI Platform",
            "body": (
                "Example startup uses AI agents and proprietary operational workflows "
                "to automate customer support."
            ),
        },
        {
            "link": "https://news.example.com/example-ai-platform",
            "kind": "news",
            "headline": "Example startup expands AI product",
            "markdown": (
                "The company reports LLM-based automation, evaluation pipelines, "
                "and production AI workflows."
            ),
        },
    ]


def _data_payloads() -> list[dict[str, str]]:
    return [
        {
            "source_url": "https://example.com/startup-data-platform",
            "type": "official",
            "name": "Example Data Platform",
            "body": (
                "Example startup uses AI to process large tabular datasets, dataframe "
                "analytics, and predictive machine learning features."
            ),
        },
        {
            "link": "https://news.example.com/example-data-platform",
            "kind": "news",
            "headline": "Example startup scales tabular AI analytics",
            "markdown": (
                "The company reports analytics pipelines for high-volume dataframes "
                "and tabular machine learning workloads."
            ),
        },
    ]


def _voice_payloads() -> list[dict[str, str]]:
    return [
        {
            "source_url": "https://example.com/startup-voice-ai",
            "type": "official",
            "name": "Example Voice AI",
            "body": (
                "Example startup uses AI voice assistants for call center automation, "
                "speech transcription, and customer support workflows."
            ),
        },
        {
            "link": "https://news.example.com/example-voice-ai",
            "kind": "news",
            "headline": "Example startup launches voice AI product",
            "markdown": (
                "The product combines ASR, TTS, and LLM summarization for voice and "
                "transcription workflows."
            ),
        },
    ]


def _healthcare_payloads() -> list[dict[str, str]]:
    return [
        {
            "source_url": "https://example.com/startup-health-ai",
            "type": "official",
            "name": "Example Health AI",
            "body": (
                "Example startup uses AI for healthcare workflow automation, medical "
                "document review, and life sciences data analysis."
            ),
        },
        {
            "link": "https://news.example.com/example-health-ai",
            "kind": "news",
            "headline": "Example startup applies AI in healthcare",
            "markdown": (
                "The company reports clinical support workflows, patient data analysis, "
                "and governance needs for medical AI."
            ),
        },
    ]


def _robotics_payloads() -> list[dict[str, str]]:
    return [
        {
            "source_url": "https://example.com/startup-robotics-ai",
            "type": "official",
            "name": "Example Robotics AI",
            "body": (
                "Example startup uses AI robotics, autonomy, simulation, and digital "
                "twins to test industrial robots."
            ),
        },
        {
            "link": "https://news.example.com/example-robotics-ai",
            "kind": "news",
            "headline": "Example startup expands robotics simulation",
            "markdown": (
                "The company reports AI-based 3D simulation workflows for autonomous "
                "robots and robotics deployment."
            ),
        },
    ]


def _latency_payloads() -> list[dict[str, str]]:
    return [
        {
            "source_url": "https://example.com/startup-inference-ai",
            "type": "official",
            "name": "Example Inference AI",
            "body": (
                "Example startup uses AI inference for LLM responses and reports "
                "latency constraints in production serving."
            ),
        },
        {
            "link": "https://news.example.com/example-inference-ai",
            "kind": "news",
            "headline": "Example startup optimizes LLM inference",
            "markdown": (
                "The company reports AI model batching, low-latency inference, and "
                "production model serving requirements."
            ),
        },
    ]


