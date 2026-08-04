"""Extrator de links de startups do InovAtiva Brasil.

Estrategia: a pagina de listagem de empresas do InovAtiva
(https://inovativabrasil.com.br/empresas/) exibe cards com links diretos
para o site de cada empresa (`<a>` externos ao dominio inovativabrasil.com.br).
Fallback: se nao encontrar links externos diretos, busca links com o
padrao `/empresas/<slug>` e extrai o campo `website` da pagina de detalhe.

Ajuste os seletores em `_CARD_LINK_SELECTOR` se o hub mudar o layout.
"""

from apps.api.src.modules.startup_discovery.application.dto import StartupCandidate
from apps.api.src.modules.startup_discovery.infrastructure.hub_extractors.base import (
    BaseHubLinkExtractor,
)

_HUB_DOMAIN = "inovativabrasil.com.br"
_CARD_LINK_SELECTOR = (
    "a.empresa-link, a[href*='empresa'], .card-empresa a, .empresa a"
)
_WEBSITE_FIELD_SELECTOR = "a.website, a[rel='nofollow external'], .site-empresa a"


class InovativaBrasilExtractor(BaseHubLinkExtractor):

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

        if external:
            return self._normalize_candidates(external)[:limit]

        # Tentativa 2: perfis internos -> extrair website de cada perfil
        profile_links = [
            (
                self._absolute_url(str(tag["href"]), listing_url),
                self._clean_text(tag.get_text(" ", strip=True)),
            )
            for tag in soup.find_all("a", href=True)
            if "/empresa" in str(tag["href"])
            and _HUB_DOMAIN in self._absolute_url(str(tag["href"]), listing_url)
        ]
        candidates: list[StartupCandidate] = []
        for profile_url, name in profile_links[:limit]:
            try:
                detail = await self._fetch(profile_url)
                description = self._description_from_detail(detail)
                for tag in detail.select(_WEBSITE_FIELD_SELECTOR):
                    href = tag.get("href", "")
                    if self._is_external(href, _HUB_DOMAIN):
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

        return self._normalize_candidates(candidates)[:limit]
