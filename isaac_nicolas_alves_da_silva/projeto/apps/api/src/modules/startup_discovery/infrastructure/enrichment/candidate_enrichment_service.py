"""Servico de enriquecimento de candidatos descobertos por nome.

Fluxo por candidato:
  1. Constroi 2 queries Tavily a partir do nome e categoria.
  2. Executa as queries em paralelo (asyncio.gather).
  3. Pontua cada URL resultado com _score_url().
  4. Seleciona a URL de maior pontuacao que nao seja dominio bloqueado.
  5. Se pontuacao >= MIN_CONFIDENCE, marca candidato como ENRICHED.
  6. Caso contrario, rejeita com reason="confidence_below_threshold".
"""

import asyncio
import re
import unicodedata
from urllib.parse import urlparse

from apps.api.src.modules.startup_discovery.application.ports import (
    WebSearchPort,
    WebSearchResult,
)
from apps.api.src.modules.startup_discovery.domain.entities import (
    StartupDiscoveryCandidate,
)
from apps.api.src.shared.logging import get_logger

logger = get_logger(__name__)

MIN_CONFIDENCE: float = 0.50

_BLOCKED_DOMAINS: frozenset[str] = frozenset(
    {
        "linkedin.com",
        "instagram.com",
        "facebook.com",
        "twitter.com",
        "x.com",
        "youtube.com",
        "github.com",
        "play.google.com",
        "apps.apple.com",
        "amazon.com",
        "amazon.com.br",
        "mercadolivre.com.br",
        "mercadolibre.com",
        "openstartups.net",
        "inovativabrasil.com.br",
        "abstartups.com.br",
        "crunchbase.com",
        "wellfound.com",
        "angel.co",
        "pitchbook.com",
        "wikipedia.org",
        "g2.com",
        "capterra.com",
        "glassdoor.com",
        "startups.com.br",
        "distrito.me",
        "endeavor.org.br",
        "latitud.com",
    }
)


def _normalize_name(name: str) -> str:
    """Lowercase, remove diacriticos, mantem apenas alfanumerico."""
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _registerable_domain(url: str) -> str:
    """Retorna dominio registravel (TLD+1 ou TLD+2 para .com.br)."""
    try:
        hostname = urlparse(url).hostname or ""
    except Exception:
        return ""
    hostname = hostname.lstrip("www.")
    parts = hostname.split(".")
    if len(parts) >= 3 and parts[-2] in {"com", "org", "net", "gov", "edu"}:
        return ".".join(parts[-3:])
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return hostname


def _is_blocked(url: str) -> bool:
    domain = _registerable_domain(url)
    return any(blocked in domain for blocked in _BLOCKED_DOMAINS)


def _score_url(
    name: str,
    normalized_name: str,
    url: str,
    title: str,
    snippet: str,
) -> float:
    """Calcula confianca (0-1) de que url e o site oficial da startup."""
    if _is_blocked(url):
        return 0.0

    domain = _registerable_domain(url)
    # Apenas a parte antes do TLD para comparacao
    domain_name = domain.split(".")[0]
    domain_name_alnum = re.sub(r"[^a-z0-9]", "", domain_name.lower())

    score = 0.0

    # +0.35: dominio contem nome normalizado
    if normalized_name and (
        normalized_name in domain_name_alnum or domain_name_alnum in normalized_name
    ):
        score += 0.35

    # +0.25: titulo menciona o nome exato (case-insensitive)
    title_lower = title.lower()
    name_lower = name.lower()
    if name_lower in title_lower:
        score += 0.25
    elif normalized_name and normalized_name in re.sub(r"[^a-z0-9]", "", title_lower):
        score += 0.15

    # +0.10: titulo comeca com o nome da startup (sinal forte de homepage)
    if title_lower.startswith(name_lower) or title_lower.startswith(normalized_name):
        score += 0.10

    # +0.10: snippet menciona o nome em contexto de empresa
    snippet_lower = snippet.lower()
    if name_lower in snippet_lower:
        score += 0.10

    # +0.10: TLD brasileiro (site oficial esperado em .com.br)
    if domain.endswith(".com.br"):
        score += 0.10
    elif domain.endswith(".ai") or domain.endswith(".io"):
        score += 0.05
    elif domain.endswith(".com"):
        score += 0.05

    return min(1.0, score)


def _build_queries(name: str, category: str | None) -> list[str]:
    queries = [
        f'"{name}" startup Brasil site oficial',
        f'"{name}" artificial intelligence startup Brazil',
    ]
    if category:
        safe_cat = category.replace("TOP 10 ", "").replace(" 2025", "").strip()
        queries.append(f'"{name}" {safe_cat} startup')
    return queries


class CandidateEnrichmentService:
    """Enriquece candidatos descobertos buscando site oficial via Tavily."""

    def __init__(self, search_port: WebSearchPort) -> None:
        self._search = search_port

    async def enrich(self, candidate: StartupDiscoveryCandidate) -> None:
        """Enriquece um candidato in-place.

        Se confianca >= MIN_CONFIDENCE -> candidate.enrich(...)
        Caso contrario -> candidate.reject("confidence_below_threshold")
        Best-effort: excecoes internas nao propagam.
        """
        try:
            await self._enrich_unsafe(candidate)
        except Exception as exc:
            logger.warning(
                "candidate enrichment failed",
                extra={"candidate": candidate.name, "reason": str(exc)},
            )
            candidate.fail(str(exc))

    async def _enrich_unsafe(self, candidate: StartupDiscoveryCandidate) -> None:
        queries = _build_queries(candidate.name, candidate.category)
        norm = _normalize_name(candidate.name)

        result_lists = await asyncio.gather(
            *[self._search.search(q, max_results=5) for q in queries],
            return_exceptions=True,
        )

        all_results: list[WebSearchResult] = []
        for r in result_lists:
            if isinstance(r, list):
                all_results.extend(r)

        best_url: str | None = None
        best_score: float = 0.0
        sources_seen: list[str] = []

        for result in all_results:
            if result.url in sources_seen:
                continue
            sources_seen.append(result.url)
            sc = _score_url(candidate.name, norm, result.url, result.title, result.snippet)
            if sc > best_score:
                best_score = sc
                best_url = result.url

        enrichment_sources = [r.url for r in all_results[:5]]

        if best_url and best_score >= MIN_CONFIDENCE:
            candidate.enrich(
                official_website_url=best_url,
                official_site_confidence=best_score,
                enrichment_sources=enrichment_sources,
            )
            logger.info(
                "candidate enriched",
                extra={
                    "startup_name": candidate.name,
                    "url": best_url,
                    "confidence": round(best_score, 3),
                },
            )
        else:
            candidate.reject(
                f"confidence_below_threshold: best={round(best_score, 3)}, url={best_url}"
            )
            logger.info(
                "candidate rejected (low confidence)",
                extra={
                    "startup_name": candidate.name,
                    "best_score": round(best_score, 3),
                    "best_url": best_url,
                },
            )

    async def enrich_batch(
        self, candidates: list[StartupDiscoveryCandidate]
    ) -> list[StartupDiscoveryCandidate]:
        """Enriquece uma lista de candidatos em paralelo."""
        await asyncio.gather(*[self.enrich(c) for c in candidates])
        return candidates
