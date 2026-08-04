"""Adapter da WOW Aceleradora (wow.ac) — primeira fonte real do Scraper.

Decisão de design documentada (o tipo de raciocínio que o projeto pede):
a página /portfolio é uma SPA. O HTML estático traz só ~4 cases em destaque;
o grid completo (~194 startups) só aparece DEPOIS do JS rodar. Por isso este
adapter usa `fetch_dynamic` (navegador), e não `fetch_static`.

Dois sinais de descoberta na página:
  - grid de logos: cada startup é um  <img alt="Nome">      -> nome
  - cases em destaque: <a href="/cases/slug">               -> nome + detail_url

Limitação conhecida do v1: a deduplicação casa o nome do grid com o slug do
case por minúsculas; nomes compostos (slug "quero-frete" vs alt "Quero Frete")
podem não casar e gerar uma entrada extra. Aceitável agora — o Extractor/
Classifier filtram relevância depois.
"""
import re
from urllib.parse import urljoin

from scraping.base import RawStartup, SourceAdapter
from scraping.fetch import fetch_dynamic

# Filtro de ruído (heurística do v1): o grid mistura logos de startup com
# elementos de UI (logo da marca, ícones, botões). Como os alts desses são
# descritivos ("Logotipo WOW...", "Ícone Fechar Menu"), filtramos por
# palavras-chave de ruído + nomes de arquivo soltos. É frágil de propósito —
# o jeito robusto seria escopar num container do grid; fica para uma evolução.
_RUIDO_ARQUIVO = re.compile(r"\.(jpe?g|png|svg|gif|webp)$", re.IGNORECASE)
_RUIDO_PALAVRAS = (
    "wow", "aceleradora", "logotipo", "logo", "ícone", "icone",
    "menu", "fechar", "banner", "background", "imagem",
)


def _eh_ruido(nome: str) -> bool:
    baixo = nome.lower()
    return bool(_RUIDO_ARQUIVO.search(nome)) or any(p in baixo for p in _RUIDO_PALAVRAS)


class WowAdapter(SourceAdapter):
    domain = "wow.ac"
    PORTFOLIO_URL = "https://www.wow.ac/portfolio"

    def discover(self) -> list[RawStartup]:
        page = fetch_dynamic(self.PORTFOLIO_URL)

        # chave (nome em minúsculas) -> RawStartup. dict preserva a ordem de
        # inserção e deduplica de forma case-insensitive.
        encontradas: dict[str, RawStartup] = {}

        # (1) grid de logos: o alt da imagem é o nome da startup
        for alt in page.css("img::attr(alt)").getall():
            nome = (alt or "").strip()
            if not nome or _eh_ruido(nome):
                continue
            encontradas.setdefault(
                nome.lower(),
                RawStartup(name=nome, source=self.domain, source_url=self.PORTFOLIO_URL),
            )

        # (2) cases em destaque: trazem um link de detalhe. Enriquece a entrada
        # do grid quando já existe; senão, cria a partir do slug.
        for a in page.css('a[href*="/cases/"]'):
            href = a.attrib.get("href")
            if not href:
                continue
            slug = href.rstrip("/").split("/")[-1]
            detail = urljoin(self.PORTFOLIO_URL, href)
            existente = encontradas.get(slug.lower())
            if existente is not None:
                existente.detail_url = detail
            else:
                encontradas[slug.lower()] = RawStartup(
                    name=slug,
                    source=self.domain,
                    source_url=self.PORTFOLIO_URL,
                    detail_url=detail,
                )

        return list(encontradas.values())


if __name__ == "__main__":
    # Execução manual para ver o scraping ao vivo:  uv run python -m scraping.wow
    # (abre um navegador real e renderiza o portfólio da WOW — precisa de rede)
    startups = WowAdapter().discover()
    print(f"\n{len(startups)} startups descobertas em wow.ac:\n")
    for s in startups:
        detalhe = f"  → {s.detail_url}" if s.detail_url else ""
        print(f"  • {s.name}{detalhe}")

