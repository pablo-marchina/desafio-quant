"""Modulo 1 - URL Discovery com pool de chaves e failover em 4 niveis.

Tavily API KEY 1 → Tavily API KEY 2 → SerpAPI KEY 1 → SerpAPI KEY 2 → None

Cada troca de chave ou falha HTTP (403/429/timeout) e registrada em log WARNING
identificando a startup afetada. Ambas as bibliotecas sao sincronas: usamos
asyncio.to_thread() para nao bloquear o event loop.

URLs retornadas sao validadas contra BLOCKED_DOMAINS antes de serem aceitas.
Cada provider monta sua propria query otimizada (Tavily usa exclude_domains
nativo; SerpAPI usa requests direto com parametros regionais BR).
"""
from __future__ import annotations

import asyncio
import urllib.parse

from ...config import get_settings
from ...logging_conf import get_logger

logger = get_logger("phase2.url_discovery")


# =============================================================================
# Blocklist de dominios inuteis para extracao
# =============================================================================

BLOCKED_DOMAINS: frozenset[str] = frozenset({
    # Redes sociais
    "linkedin.com", "instagram.com", "youtube.com", "facebook.com",
    "twitter.com", "x.com", "tiktok.com", "pinterest.com",
    # Diretorios e agregadores de startups
    "crunchbase.com", "tracxn.com", "wikipedia.org",
    "startups.com.br", "projetodraft.com", "neofeed.com.br",
    "startse.com", "distrito.me", "openstartups.net",
    "captable.com.br", "startupslatam.com", "abria.org.br",
    "onpost.com.br", "braziljournal.com", "techcrunch.com",
    "sdgs.un.org",
    # Lojas e plataformas de distribuicao
    "apps.apple.com", "play.google.com", "amazon.com",
    # Imprensa e noticias genericas
    "reuters.com", "valor.com.br", "exame.com", "folha.uol.com.br",
    "estadao.com.br", "g1.globo.com", "infomoney.com.br",
    # Motores de busca e redirecionamento
    "google.com", "bing.com", "duckduckgo.com",
    # Job boards e perfis de pessoas
    "glassdoor.com", "indeed.com", "peopleforce.io",
    "catho.com.br", "vagas.com.br",
    # Formularios e plataformas SaaS genericas
    "zohopublic.com", "typeform.com", "forms.gle",
    # Plataformas de portfolios de VC (nao sao o site da startup)
    "setpesp.org.br", "maristabrasil.org", "vibraenergia.com.br",
    "rio.websummit.com", "gympass.com", "didiglobal.com",
    "healthcaretechoutlook.com", "partners-official.com",
    # Noticias e portais locais
    "grupoabcnews.com.br", "jusbrasil.com.br",
})

_BLOCKED_EXTENSIONS: frozenset[str] = frozenset({
    ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".mp4", ".mp3", ".xls", ".xlsx", ".doc", ".docx",
})


def _is_blocked(url: str) -> bool:
    """True se o dominio esta na blocklist, URL e arquivo estatico ou esta malformada."""
    if not url:
        return True
    try:
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        path = parsed.path.lower()
        if any(path.endswith(ext) for ext in _BLOCKED_EXTENSIONS):
            return True
        # Match exato ou subdominio: "en.wikipedia.org" bate "wikipedia.org"
        return any(netloc == d or netloc.endswith("." + d) for d in BLOCKED_DOMAINS)
    except Exception:
        return True


# =============================================================================
# Providers de busca (sincronos — chamados via asyncio.to_thread)
# =============================================================================

def _tavily_search(api_key: str, startup_name: str, sector: str) -> str | None:
    """Busca via Tavily com exclude_domains nativo e query enriquecida com setor."""
    from tavily import TavilyClient

    client = TavilyClient(api_key=api_key)
    if sector and sector not in ("(descoberta - QFirst)", "Portfolio VC"):
        query = f"{startup_name} {sector} startup Brasil"
    else:
        query = f"{startup_name} startup Brasil site oficial"

    resp = client.search(
        query=query,
        max_results=7,
        search_depth="basic",
        exclude_domains=list(BLOCKED_DOMAINS),
    )
    for r in resp.get("results") or []:
        url = r.get("url", "")
        if url and not _is_blocked(url):
            return url
    return None


def _serpapi_search(api_key: str, startup_name: str, sector: str) -> str | None:
    """Busca via Serper.dev (google.serper.dev) com parametros regionais BR.

    Usa POST + header X-API-KEY — formato nativo da API Serper.dev.
    Fallback interno para query mais curta se a primaria retornar vazio.
    """
    import requests as _req

    _BASE = "https://google.serper.dev/search"
    primary = (
        f"{startup_name} {sector} startup Brasil site oficial"
        if sector and sector not in ("(descoberta - QFirst)", "Portfolio VC")
        else f"{startup_name} startup Brasil site oficial"
    )
    queries = [primary, f"{startup_name} empresa Brasil"]

    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    for query in queries:
        payload = {"q": query, "gl": "br", "hl": "pt", "num": 7}
        try:
            resp = _req.post(_BASE, json=payload, headers=headers, timeout=12)
            resp.raise_for_status()
            for r in (resp.json().get("organic") or []):
                url = r.get("link", "")
                if url and not _is_blocked(url):
                    return url
        except Exception as exc:
            logger.warning("Serper query '%s' falhou: %s", query, exc)
            break  # auth/timeout: nao tenta a segunda query
    return None


# =============================================================================
# Logica de failover
# =============================================================================

async def _try_provider(
    fn,
    key_label: str,
    startup_name: str,
    sector: str,
    key: str,
) -> str | None:
    """Executa o provider sincrono em thread pool e trata excecoes."""
    try:
        result = await asyncio.to_thread(fn, key, startup_name, sector)
        if result:
            logger.info("URL encontrada via %s para '%s': %s", key_label, startup_name, result)
        return result
    except Exception as exc:
        status_hint = ""
        msg = str(exc)
        if "429" in msg or "rate" in msg.lower() or "quota" in msg.lower():
            status_hint = " (quota/rate-limit)"
        elif "403" in msg or "401" in msg or "unauthorized" in msg.lower():
            status_hint = " (chave invalida/sem saldo)"
        elif "timeout" in msg.lower() or "connect" in msg.lower():
            status_hint = " (timeout)"
        logger.warning(
            "Falha em %s%s para startup '%s': %s",
            key_label, status_hint, startup_name, exc,
        )
        return None


async def _discover_startup_url_impl(startup_name: str, sector: str) -> str | None:
    """Implementacao interna do algoritmo de failover em 4 niveis."""
    settings = get_settings()

    levels: list[tuple[str, object, str | None]] = [
        ("Tavily KEY_1",  _tavily_search,  settings.tavily_api_key_1),
        ("Tavily KEY_2",  _tavily_search,  settings.tavily_api_key_2),
        ("SerpAPI KEY_1", _serpapi_search, settings.serpapi_api_key_1),
        ("SerpAPI KEY_2", _serpapi_search, settings.serpapi_api_key_2),
    ]

    prev_label: str | None = None
    for label, fn, key in levels:
        if not key:
            logger.info("Chave %s nao configurada; pulando nivel.", label)
            continue
        if prev_label:
            logger.warning(
                "Rotacao de chave [%s → %s] para startup '%s'.",
                prev_label, label, startup_name,
            )
        result = await _try_provider(fn, label, startup_name, sector, key)
        if result:
            return result
        prev_label = label

    logger.warning(
        "Todas as chaves esgotadas para '%s' (%s). URL nao encontrada.",
        startup_name, sector,
    )
    return None


# =============================================================================
# Tool LangGraph (@tool decorator — lazy import)
# =============================================================================

try:
    from langchain_core.tools import tool as _lc_tool

    @_lc_tool
    async def discover_startup_url(startup_name: str, sector: str) -> str | None:
        """Descobre a URL oficial de uma startup brasileira via busca web.

        Utiliza failover automatico entre Tavily (2 chaves) e SerpAPI (2 chaves).
        URLs de redes sociais, diretorios e arquivos estaticos sao automaticamente
        rejeitadas pela blocklist BLOCKED_DOMAINS.
        Retorna a URL encontrada ou None se todas as tentativas falharem.
        O status 'missing_url' deve ser gravado pelo orquestrador em caso de None.
        """
        return await _discover_startup_url_impl(startup_name, sector)

except ImportError:
    logger.warning(
        "langchain-core ausente: discover_startup_url nao sera decorada com @tool. "
        "Instale requirements-phase2.txt para habilitar integracao LangGraph."
    )

    async def discover_startup_url(startup_name: str, sector: str) -> str | None:  # type: ignore[misc]
        """Versao sem @tool (langchain-core nao instalado)."""
        return await _discover_startup_url_impl(startup_name, sector)
