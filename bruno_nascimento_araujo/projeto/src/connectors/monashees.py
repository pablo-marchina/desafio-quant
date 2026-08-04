"""Conector E - Monashees (Regex sobre arquivo binario do Framer CMS).

O site usa Framer, que serve um arquivo compilado/compactado (BSON/MessagePack
parcial). As strings textuais estao intactas, mas cercadas por caracteres de
controle (\\x00, metadados de layout). Tratamos como texto plano e usamos regex
robustas para extrair URLs / nomes / descricoes, limpando o ruido binario.
"""
from __future__ import annotations

import re

from ..models import StartupRecord, registered_domain
from .base import BaseConnector

MONASHEES_URL = (
    "https://framerusercontent.com/cms/VrqXwf4HIKk8QTSs16VX/"
    "Am9agj2u21FE4TGQ1eJK/Id3uLm6hk-chunk-default-0.framercms?range=0-120356"
)

# --- Regex isoladas (fonte MAIS fragil: bytes de controle no meio do texto) ---
# Remove bytes de controle/nulos antes de qualquer parsing textual.
REGEX_CONTROL_CHARS = re.compile(rb"[\x00-\x08\x0b\x0c\x0e-\x1f]")
# URLs http(s) de startups (ignoramos assets do proprio framer).
REGEX_FRAMER_URLS = re.compile(r"https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+")
# Nomes "limpos": sequencia de palavras com inicial maiuscula (heuristica).
REGEX_FRAMER_NAMES = re.compile(r"[A-Z][A-Za-z0-9&.\- ]{2,60}")

# Dominios que sao infra/asset e nao startups de portfolio.
_IGNORED_DOMAINS = {
    "framerusercontent.com",
    "framer.com",
    "framer.app",
    "google.com",
    "gstatic.com",
    "fonts.googleapis.com",
    "youtube.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "facebook.com",
    "instagram.com",
}


def _clean_text(raw: bytes) -> str:
    """Substitui bytes de controle por espaco e decodifica de forma tolerante."""
    scrubbed = REGEX_CONTROL_CHARS.sub(b" ", raw)
    return scrubbed.decode("utf-8", errors="ignore")


class MonasheesConnector(BaseConnector):
    source_name = "Monashees"

    async def fetch(self) -> list[StartupRecord]:
        raw = await self.fetcher.get_bytes(MONASHEES_URL)
        if not raw:
            return []
        text = _clean_text(raw)

        records: list[StartupRecord] = []
        seen_domains: set[str] = set()
        for match in REGEX_FRAMER_URLS.finditer(text):
            url = match.group(0).rstrip(".,);'\"")
            domain = registered_domain(url)
            if not domain or domain in _IGNORED_DOMAINS or domain in seen_domains:
                continue
            seen_domains.add(domain)

            # Nome derivado do contexto textual imediatamente anterior a URL.
            window = text[max(0, match.start() - 80):match.start()]
            name = self._guess_name(window) or domain.split(".")[0].capitalize()
            try:
                records.append(
                    StartupRecord(
                        name=name,
                        sector="Portfolio VC",
                        official_website=url,
                        source_name=self.source_name,
                        source_url=MONASHEES_URL,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                self.log.debug("Registro ignorado em Monashees: %s", exc)
        return records

    @staticmethod
    def _guess_name(window: str) -> str | None:
        candidates = REGEX_FRAMER_NAMES.findall(window)
        if not candidates:
            return None
        # O texto mais proximo da URL costuma ser o nome da startup.
        return candidates[-1].strip()
