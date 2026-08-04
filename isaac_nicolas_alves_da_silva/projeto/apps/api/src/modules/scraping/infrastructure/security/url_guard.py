"""Validação de URLs para reduzir riscos de Server-Side Request Forgery."""

import ipaddress
import socket
from urllib.parse import urlparse

from apps.api.src.modules.scraping.domain.exceptions import UnsafeUrlError


class UrlGuard:
    """Bloqueia URLs capazes de alcançar recursos internos ou esquemas perigosos.

    SSRF ocorre quando um usuário fornece uma URL e induz o servidor a acessar
    destinos internos em seu nome, como localhost, banco de dados ou metadados
    de uma infraestrutura de nuvem.
    """

    allowed_schemes = {"http", "https"}
    blocked_hostnames = {"localhost", "localhost.localdomain"}

    async def validate(self, url: str) -> None:
        """Valida formato, hostname e endereços resolvidos por DNS."""

        parsed = urlparse(url)

        if parsed.scheme.lower() not in self.allowed_schemes:
            raise UnsafeUrlError("Somente URLs HTTP e HTTPS são permitidas.")

        if not parsed.hostname:
            raise UnsafeUrlError("A URL precisa possuir um hostname.")

        hostname = parsed.hostname.lower().rstrip(".")
        if hostname in self.blocked_hostnames:
            raise UnsafeUrlError("Acesso a localhost não é permitido.")

        # Se o hostname já for um IP, podemos validá-lo diretamente.
        try:
            direct_ip = ipaddress.ip_address(hostname)
        except ValueError:
            direct_ip = None

        if direct_ip is not None:
            self._validate_ip(direct_ip)
            return

        # Um domínio público pode resolver para um IP privado. Por isso, não
        # basta validar apenas o texto da URL: também verificamos o resultado
        # atual do DNS antes da requisição.
        try:
            address_info = await self._resolve_hostname(hostname)
        except socket.gaierror as error:
            raise UnsafeUrlError(
                "Não foi possível resolver o hostname informado."
            ) from error

        if not address_info:
            raise UnsafeUrlError("O hostname não resolveu para nenhum endereço.")

        for address in address_info:
            self._validate_ip(ipaddress.ip_address(address))

    async def _resolve_hostname(self, hostname: str) -> set[str]:
        """Resolve o hostname sem bloquear o event loop da aplicação."""

        import asyncio

        loop = asyncio.get_running_loop()
        results = await loop.getaddrinfo(
            hostname,
            None,
            type=socket.SOCK_STREAM,
        )

        # O endereço IP fica na primeira posição da estrutura ``sockaddr``.
        return {result[4][0] for result in results}

    @staticmethod
    def _validate_ip(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
        """Recusa endereços que não devem ser acessados pelo scraper."""

        if not address.is_global:
            raise UnsafeUrlError(
                f"O endereço {address} não é um destino público permitido."
            )
