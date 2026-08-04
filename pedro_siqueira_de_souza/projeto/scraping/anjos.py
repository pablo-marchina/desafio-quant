"""Adapter do Anjos do Brasil (anjosdobrasil.net) — fonte estática.

Decisão de design documentada: diferente da WOW e da 100 Open (que são SPAs e
exigem navegador), a página /cases-de-sucesso/ entrega os nomes no HTML
estático — cada startup é um <img alt="Nome">. Logo usamos `fetch_static`
(HTTP puro), o fetcher mais barato. É o caso ideal: comece sempre pelo barato.

São "cases de sucesso" (startups já adquiridas), então é uma amostra pequena e
curada — útil como sinal de qualidade, não de volume.
"""
import re

from scraping.base import RawStartup, SourceAdapter
from scraping.fetch import fetch_static

CASES_URL = "https://anjosdobrasil.net/cases-de-sucesso/"

# alts que NÃO são startups: pixel do Facebook, logo da marca, nomes de arquivo.
_RUIDO_ARQUIVO = re.compile(r"\.(jpe?g|png|svg|gif|webp)$", re.IGNORECASE)
_RUIDO_PALAVRAS = ("anjos", "logo", "fbpx", "pixel")


def _eh_ruido(nome: str) -> bool:
    baixo = nome.lower()
    return bool(_RUIDO_ARQUIVO.search(nome)) or any(p in baixo for p in _RUIDO_PALAVRAS)


class AnjosAdapter(SourceAdapter):
    domain = "anjosdobrasil.net"

    def discover(self) -> list[RawStartup]:
        page = fetch_static(CASES_URL)

        encontradas: dict[str, RawStartup] = {}
        for alt in page.css("img::attr(alt)").getall():
            nome = (alt or "").strip()
            if not nome or _eh_ruido(nome):
                continue
            encontradas.setdefault(
                nome.lower(),
                RawStartup(name=nome, source=self.domain, source_url=CASES_URL),
            )
        return list(encontradas.values())


if __name__ == "__main__":
    # Execução manual:  uv run python -m scraping.anjos
    startups = AnjosAdapter().discover()
    print(f"\n{len(startups)} startups descobertas em anjosdobrasil.net:\n")
    for s in startups:
        print(f"  • {s.name}")
