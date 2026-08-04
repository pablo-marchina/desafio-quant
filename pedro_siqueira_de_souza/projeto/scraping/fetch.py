"""Camada de fetch do Scraper — a "costura" (seam) que os testes trocam.

Os adapters NUNCA chamam o Scrapling direto; chamam `fetch_static` /
`fetch_dynamic` daqui. Isso (a) centraliza o tratamento de erro num lugar só
e (b) permite trocar a rede por HTML salvo nos testes via `monkeypatch`, do
mesmo jeito que `get_llm` é trocado por um FakeLLM (ver agents/README.md).

Qual fetcher usar — sempre tente o mais barato primeiro:
  - fetch_static  -> Fetcher        : HTTP puro com fingerprint TLS. Rápido e
                                      barato; serve para HTML estático e APIs.
  - fetch_dynamic -> DynamicFetcher : abre um navegador real e executa o JS.
                                      Necessário em sites SPA — a maioria dos
                                      diretórios/portfólios brasileiros só
                                      revela a lista de startups DEPOIS do JS.

(O StealthyFetcher, para anti-bot/Cloudflare, fica reservado para quando uma
fonte realmente exigir — é o mais lento dos três.)
"""
from loguru import logger
from scrapling.fetchers import DynamicFetcher, Fetcher

from scraping.base import ScrapeError


def fetch_static(url: str, timeout: int = 20):
    """GET via HTTP puro (Scrapling `Fetcher`). Para HTML estático/APIs."""
    try:
        return Fetcher.get(url, timeout=timeout)
    except Exception as e:  # rede/timeout/TLS — empacota num erro do domínio
        logger.error("fetch_static falhou em {}: {}", url, e)
        raise ScrapeError(f"fetch_static falhou em {url}") from e


def fetch_dynamic(url: str, network_idle: bool = True, timeout: int = 60000):
    """Render com navegador (Scrapling `DynamicFetcher`). Para sites SPA/JS."""
    try:
        return DynamicFetcher.fetch(url, network_idle=network_idle, timeout=timeout)
    except Exception as e:
        logger.error("fetch_dynamic falhou em {}: {}", url, e)
        raise ScrapeError(f"fetch_dynamic falhou em {url}") from e
