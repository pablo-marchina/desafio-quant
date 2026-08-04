"""Validacao de robots.txt com cache por dominio.

Regra de seguranca: se o robots.txt nao puder ser obtido (404, timeout, erro),
assumimos permissao de crawl (log INFO). Dominio de user-agent testado: '*'.
"""
from __future__ import annotations

from urllib.parse import urlparse

from ..http_client import PoliteFetcher
from ..logging_conf import get_logger

logger = get_logger("phase2.robots")


class RobotsChecker:
    """Cache de regras de robots.txt por dominio.

    Uma instancia por sessao de scraping: evita re-fetchar o mesmo robots.txt
    para startups no mesmo dominio (raro, mas possivel em portfolios VC).
    """

    def __init__(self) -> None:
        self._cache: dict[str, object] = {}  # domain → parser ou sentinel "allow_all"

    def _domain_of(self, url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    async def is_allowed(self, url: str, fetcher: PoliteFetcher) -> bool:
        """Retorna True se o crawl da URL e permitido pelo robots.txt."""
        domain = self._domain_of(url)
        path = urlparse(url).path or "/"

        if domain not in self._cache:
            await self._load(domain, fetcher)

        parser = self._cache[domain]
        if parser == "allow_all":
            return True

        try:
            allowed: bool = parser.is_allowed("*", path)  # type: ignore[union-attr]
            if not allowed:
                logger.warning("robots.txt bloqueia crawl em %s (path: %s).", domain, path)
            return allowed
        except Exception as exc:
            logger.info("Erro ao verificar robots para %s: %s — permitindo.", url, exc)
            return True

    async def _load(self, domain: str, fetcher: PoliteFetcher) -> None:
        robots_url = f"{domain}/robots.txt"
        content = await fetcher.get_text(robots_url)
        if not content:
            logger.info("robots.txt nao encontrado em %s — crawl permitido.", domain)
            self._cache[domain] = "allow_all"
            return
        try:
            from robotexclusionrulesparser import RobotExclusionRulesParser

            parser = RobotExclusionRulesParser()
            parser.parse(content)
            self._cache[domain] = parser
        except ImportError:
            logger.warning(
                "robotexclusionrulesparser ausente: ignorando robots.txt de %s. "
                "Instale requirements-phase2.txt para validacao completa.",
                domain,
            )
            self._cache[domain] = "allow_all"
        except Exception as exc:
            logger.info("Falha ao parsear robots.txt de %s: %s — permitindo.", domain, exc)
            self._cache[domain] = "allow_all"
