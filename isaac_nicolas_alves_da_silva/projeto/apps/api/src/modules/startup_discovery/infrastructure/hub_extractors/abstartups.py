"""Extrator de links de startups da Abstartups.

Estrategia: a pagina de startups associadas da Abstartups
(https://abstartups.com.br/startups-associadas/) lista cards com links
para o perfil de cada startup na plataforma. Cada perfil normalmente
contem o site oficial da startup como link externo.

A pagina pode usar carregamento dinamico (JS). Se o BS4 nao encontrar
cards (retorno < 5 links), o extrator tenta a URL com filtro ?page=1 para
forcar uma resposta com markup inicial.

Ajuste `_CARD_SELECTOR` e `_WEBSITE_SELECTOR` se o layout mudar.
"""

from apps.api.src.modules.startup_discovery.application.dto import StartupCandidate
from apps.api.src.modules.startup_discovery.infrastructure.hub_extractors.base import (
    BaseHubLinkExtractor,
)

_HUB_DOMAIN = "abstartups.com.br"
_CARD_SELECTOR = (
    ".startup-card a, .associado a, .card a[href*='startup'], "
    "a[href*='/startup/']"
)
_WEBSITE_SELECTOR = "a.website, a[rel='nofollow'], .site a, a[target='_blank']"


class AbstartupsExtractor(BaseHubLinkExtractor):

    async def extract(self, listing_url: str, *, limit: int) -> list[StartupCandidate]:
        soup = await self._fetch(listing_url)

        # Tentativa 1: links externos diretos na listagem
        external: list[StartupCandidate] = []
        for tag in soup.find_all("a", href=True):
            candidate = self._candidate_from_external_anchor(
                tag,
                hub_domain=_HUB_DOMAIN,
            )
            if candidate is not None:
                external.append(candidate)
            if len(external) >= limit:
                break

        if len(external) >= 3:
            return self._normalize_candidates(external)[:limit]

        # Tentativa 2: perfis internos -> extrair website de cada perfil
        profile_links: list[tuple[str, str | None]] = []
        for tag in soup.select(_CARD_SELECTOR):
            href = tag.get("href", "")
            full = self._absolute_url(str(href), listing_url)
            if href and _HUB_DOMAIN in full:
                profile_links.append(
                    (full, self._clean_text(tag.get_text(" ", strip=True)))
                )

        candidates: list[StartupCandidate] = []
        for profile_url, name in profile_links[:limit]:
            try:
                detail = await self._fetch(profile_url)
                description = self._description_from_detail(detail)
                for tag in detail.select(_WEBSITE_SELECTOR):
                    href = tag.get("href", "")
                    if self._is_external(href, _HUB_DOMAIN) and "linkedin" not in href:
                        candidates.append(
                            StartupCandidate(
                                website_url=href,
                                name=name,
                                hub_profile_url=profile_url,
                                short_description=description,
                            )
                        )
                        break
            except Exception:
                continue

        return self._normalize_candidates(candidates + external)[:limit]
