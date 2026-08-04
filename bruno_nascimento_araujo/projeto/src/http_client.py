"""Cliente HTTP assincrono compartilhado com retry e controle de politeness.

Os conectores e a busca aberta NUNCA usam o httpx.AsyncClient cru: passam pelo
PoliteFetcher, que combina:
  - httpx.Limits (teto global de conexoes);
  - asyncio.Semaphore (concorrencia efetiva por execucao);
  - asyncio.sleep com jitter (atraso dinamico entre requisicoes).
Sem isso, baixar a homepage de centenas de startups na fase aberta queimaria o IP.
"""
from __future__ import annotations

import asyncio
import random

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import Settings, get_settings
from .logging_conf import get_logger

logger = get_logger("http")

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

# Pool de User-Agents para o cliente de extracao profunda (Fase 2).
# Rotacionados aleatoriamente para evitar fingerprinting basico.
_UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]

# Erros transitorios que justificam retry.
_RETRYABLE = (httpx.TransportError, httpx.HTTPStatusError)


def make_client(settings: Settings | None = None) -> httpx.AsyncClient:
    settings = settings or get_settings()
    return httpx.AsyncClient(
        timeout=settings.request_timeout,
        follow_redirects=True,
        headers=_DEFAULT_HEADERS,
        limits=httpx.Limits(
            max_connections=settings.max_connections,
            max_keepalive_connections=max(2, settings.max_connections // 4),
        ),
    )


def make_deep_client() -> httpx.AsyncClient:
    """Cliente para extracao profunda (Fase 2): UA rotativo + timeout restrito.

    Cria um novo cliente com UA aleatorio do pool. Para rotacao por request,
    o chamador pode fazer client.headers.update({'User-Agent': random.choice(_UA_POOL)}).
    """
    return httpx.AsyncClient(
        timeout=httpx.Timeout(15.0, connect=5.0),
        follow_redirects=True,
        headers={
            "User-Agent": random.choice(_UA_POOL),
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
    )


class PoliteFetcher:
    """Envolve um httpx.AsyncClient com semaforo + atraso por jitter.

    Os metodos get_text/get_json/get_bytes NUNCA propagam excecao de rede: logam
    e retornam None, para que a falha de uma fonte nao derrube o pipeline.
    """

    def __init__(self, client: httpx.AsyncClient, settings: Settings | None = None) -> None:
        self._client = client
        self._settings = settings or get_settings()
        self._sem = asyncio.Semaphore(self._settings.per_host_concurrency)

    @property
    def client(self) -> httpx.AsyncClient:
        return self._client

    async def _sleep_jitter(self) -> None:
        lo, hi = self._settings.polite_delay_min, self._settings.polite_delay_max
        if hi > 0:
            await asyncio.sleep(random.uniform(lo, max(lo, hi)))

    @retry(
        retry=retry_if_exception_type(_RETRYABLE),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
        reraise=True,
    )
    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        async with self._sem:
            await self._sleep_jitter()
            resp = await self._client.request(method, url, **kwargs)
            resp.raise_for_status()
            return resp

    async def get_text(self, url: str, **kwargs) -> str | None:
        try:
            resp = await self._request("GET", url, **kwargs)
            return resp.text
        except Exception as exc:  # noqa: BLE001 - isolamento intencional
            logger.warning("GET texto falhou em %s: %s", url, exc)
            return None

    async def get_bytes(self, url: str, **kwargs) -> bytes | None:
        try:
            resp = await self._request("GET", url, **kwargs)
            return resp.content
        except Exception as exc:  # noqa: BLE001
            logger.warning("GET bytes falhou em %s: %s", url, exc)
            return None

    async def get_json(self, url: str, **kwargs):
        try:
            resp = await self._request("GET", url, **kwargs)
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("GET json falhou em %s: %s", url, exc)
            return None
