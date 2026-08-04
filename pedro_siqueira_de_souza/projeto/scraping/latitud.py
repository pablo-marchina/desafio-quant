"""Adapter da Latitud (latitud.com) — descoberta por link externo.

Decisão de design documentada: a página /portfolio é um site Framer que NÃO
expõe os nomes em texto nem em `alt`, e nem busca os dados de uma API (capturei
a rede: só um token de auth do Framer). O sinal que sobra são os ~85 links
que apontam para os SITES OFICIAIS das investidas (salvy.com.br, datanomik.com,
agentastra.ai...). Então a técnica aqui é diferente das outras fontes:

  derivar o nome a partir do domínio do link externo.

Bônus: o próprio link já é o site oficial da startup (o "Grupo B" de
enriquecimento) — guardamos como detail_url de graça.

Heurística (v1): consideramos investida todo link externo para a RAIZ de um
domínio (path vazio ou "/"), excluindo redes sociais/CDNs. Frágil de propósito;
o nome derivado do domínio (minúsculo) é um sinal cru — o Extractor normaliza.
"""
from urllib.parse import urlparse

from scraping.base import RawStartup, SourceAdapter
from scraping.fetch import fetch_dynamic

PORTFOLIO_URL = "https://www.latitud.com/portfolio"

# hosts que não são investidas (a própria Latitud, redes, infra do Framer).
_HOSTS_RUIDO = (
    "latitud", "framer", "google", "gstatic", "linkedin", "instagram",
    "twitter", "x.com", "facebook", "youtube", "calendly", "typeform",
    "notion", "spotify", "apple", "whatsapp", "medium",
)


def _nome_do_host(host: str) -> str:
    """Primeiro rótulo do domínio: 'www.salvy.com.br' -> 'salvy'."""
    if host.startswith("www."):
        host = host[4:]
    return host.split(".")[0]


class LatitudAdapter(SourceAdapter):
    domain = "latitud.com"

    def discover(self) -> list[RawStartup]:
        page = fetch_dynamic(PORTFOLIO_URL)

        encontradas: dict[str, RawStartup] = {}
        for href in page.css("a::attr(href)").getall():
            href = (href or "").strip()
            if not href.startswith("http"):
                continue
            parsed = urlparse(href)
            host = parsed.netloc.lower()
            if not host or any(r in host for r in _HOSTS_RUIDO):
                continue
            # só a raiz do site (investida), não links profundos (artigos etc.)
            if parsed.path not in ("", "/"):
                continue
            nome = _nome_do_host(host)
            encontradas.setdefault(
                nome,
                RawStartup(
                    name=nome,
                    source=self.domain,
                    source_url=PORTFOLIO_URL,
                    detail_url=f"{parsed.scheme}://{host}",
                ),
            )
        return list(encontradas.values())


if __name__ == "__main__":
    # Execução manual:  uv run python -m scraping.latitud
    startups = LatitudAdapter().discover()
    print(f"\n{len(startups)} startups descobertas em latitud.com:\n")
    for s in startups:
        print(f"  • {s.name}  → {s.detail_url}")
