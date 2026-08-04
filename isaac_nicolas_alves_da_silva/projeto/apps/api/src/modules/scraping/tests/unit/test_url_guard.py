"""Testes unitários da proteção de URLs contra SSRF."""

import pytest

from apps.api.src.modules.scraping.domain.exceptions import UnsafeUrlError
from apps.api.src.modules.scraping.infrastructure.security.url_guard import UrlGuard


class FakeDnsUrlGuard(UrlGuard):
    """UrlGuard que usa respostas DNS configuradas pelo teste."""

    def __init__(self, addresses: set[str]) -> None:
        self.addresses = addresses

    async def _resolve_hostname(self, hostname: str) -> set[str]:
        return self.addresses


@pytest.mark.anyio
@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/file",
        "javascript:alert(1)",
    ],
)
async def test_blocks_non_http_schemes(url: str) -> None:
    """O scraper deve aceitar somente HTTP e HTTPS."""

    with pytest.raises(UnsafeUrlError, match="HTTP e HTTPS"):
        await UrlGuard().validate(url)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/admin",
        "http://localhost.localdomain/admin",
        "http://127.0.0.1",
        "http://192.168.1.10",
        "http://10.0.0.1",
        "http://169.254.169.254/latest/meta-data",
    ],
)
async def test_blocks_local_private_and_metadata_addresses(url: str) -> None:
    """Destinos internos não podem ser acessados diretamente."""

    with pytest.raises(UnsafeUrlError):
        await UrlGuard().validate(url)


@pytest.mark.anyio
async def test_blocks_public_hostname_that_resolves_to_private_ip() -> None:
    """Um domínio aparentemente público ainda pode apontar para a rede interna."""

    guard = FakeDnsUrlGuard({"192.168.1.20"})

    with pytest.raises(UnsafeUrlError, match="não é um destino público"):
        await guard.validate("https://site-malicioso.example")


@pytest.mark.anyio
async def test_allows_hostname_when_all_resolved_ips_are_public() -> None:
    """Domínio é permitido quando todos os IPs resolvidos são globais."""

    guard = FakeDnsUrlGuard({"93.184.216.34", "2606:2800:220:1:248:1893:25c8:1946"})

    await guard.validate("https://example.com")
