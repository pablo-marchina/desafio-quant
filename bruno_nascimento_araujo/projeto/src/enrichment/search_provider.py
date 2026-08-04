"""Busca aberta (QFirst): geracao de candidatas por expansao de grafo de links.

Estrategia gratuita e autocontida (default):
  1. Sementes = sites oficiais ja validados no banco.
  2. Baixa a homepage de cada semente e extrai links de saida (href) para
     dominios EXTERNOS.
  3. Cada novo dominio vira uma Candidate; coletamos titulo + meta-description
     para o QFirst pontuar.

A interface BaseSearchProvider e extensivel: para plugar uma API comercial
(Tavily, Serper, ...) basta herdar e implementar discover(), lendo a chave do
.env, SEM tocar no motor principal (ver TavilyProvider abaixo, stub).
"""
from __future__ import annotations

import abc
import asyncio
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..config import Settings, get_settings
from ..http_client import PoliteFetcher
from ..logging_conf import get_logger
from ..models import Candidate, registered_domain
from .spa_fallback import _fetch_static

logger = get_logger("search")

# Dominios que nao sao "startups alvo" (redes sociais, CDNs, infra comum).
_SKIP_DOMAINS = {
    "google.com", "gstatic.com", "googleapis.com", "youtube.com", "youtu.be",
    "linkedin.com", "twitter.com", "x.com", "facebook.com", "instagram.com",
    "tiktok.com", "wa.me", "whatsapp.com", "maps.google.com", "cdn.jsdelivr.net",
    "fonts.googleapis.com", "fonts.gstatic.com", "github.com", "medium.com",
    "vimeo.com", "spotify.com", "apple.com", "play.google.com",
}


class BaseSearchProvider(abc.ABC):
    """Contrato de um provedor de candidatas para a busca aberta."""

    def __init__(self, fetcher: PoliteFetcher, settings: Settings | None = None) -> None:
        self.fetcher = fetcher
        self.settings = settings or get_settings()

    @abc.abstractmethod
    async def discover(self, seeds: list[str]) -> list[Candidate]:
        ...


class LinkExpansionProvider(BaseSearchProvider):
    """Provedor default: expande o grafo seguindo links de saida das sementes."""

    async def discover(self, seeds: list[str]) -> list[Candidate]:
        if not seeds:
            logger.info("Sem sementes no banco; busca aberta pulada.")
            return []
        logger.info("Expandindo grafo a partir de %d sementes.", len(seeds))

        results = await asyncio.gather(
            *(self._outbound_links(seed) for seed in seeds), return_exceptions=True
        )
        candidate_urls: dict[str, str] = {}  # dominio -> url (dedupe por dominio)
        seed_domains = {registered_domain(s) for s in seeds}
        for res in results:
            if isinstance(res, Exception):
                continue
            seed_url, links = res
            for link in links:
                dom = registered_domain(link)
                if not dom or dom in seed_domains or dom in candidate_urls:
                    continue
                if any(dom == s or dom.endswith("." + s) for s in _SKIP_DOMAINS):
                    continue
                candidate_urls[dom] = link

        max_c = self.settings.open_search_max_candidates
        chosen = list(candidate_urls.values())[:max_c]
        logger.info(
            "%d dominios externos unicos; avaliando %d candidatos.",
            len(candidate_urls), len(chosen),
        )

        enriched = await asyncio.gather(
            *(self._build_candidate(url) for url in chosen), return_exceptions=True
        )
        return [c for c in enriched if isinstance(c, Candidate)]

    async def _outbound_links(self, seed: str) -> tuple[str, list[str]]:
        html = await self.fetcher.get_text(seed)
        if not html:
            return seed, []
        soup = BeautifulSoup(html, "lxml")
        seed_dom = registered_domain(seed)
        links: list[str] = []
        for a in soup.find_all("a", href=True):
            href = urljoin(seed, a["href"].strip())
            if not href.lower().startswith("http"):
                continue
            if registered_domain(href) != seed_dom:
                links.append(href)
        return seed, links

    async def _build_candidate(self, url: str) -> Candidate | None:
        """Coleta titulo + meta-description; usa fallback estatico se preciso."""
        html = await self.fetcher.get_text(url)
        title, description = "", ""
        if html:
            soup = BeautifulSoup(html, "lxml")
            if soup.title and soup.title.string:
                title = soup.title.string.strip()
            meta = soup.find("meta", attrs={"name": "description"}) or soup.find(
                "meta", attrs={"property": "og:description"}
            )
            if meta and meta.get("content"):
                description = meta["content"].strip()
        # Se nada de util veio do estatico, tenta o texto limpo (cobre SPAs).
        if not title and not description:
            text = await _fetch_static(url, self.fetcher)
            description = (text or "")[:500]
            if not description:
                return None
        domain = registered_domain(url) or url
        return Candidate(
            url=url,
            title=title or domain,
            description=description,
            source_url=url,
        )


class TavilyProvider(BaseSearchProvider):
    """STUB de exemplo: provider comercial via API.

    Para ativar: instale o cliente desejado, defina TAVILY_API_KEY no .env e
    implemente discover() consumindo a API. O motor principal aceita qualquer
    BaseSearchProvider sem alteracoes.
    """

    async def discover(self, seeds: list[str]) -> list[Candidate]:  # pragma: no cover
        if not self.settings.tavily_api_key:
            logger.warning("TAVILY_API_KEY ausente; TavilyProvider inativo.")
            return []
        raise NotImplementedError(
            "Implemente a chamada a API de busca aqui e retorne list[Candidate]."
        )
