"""Parsing estruturado de HTML simples via BeautifulSoup (F1.5).

Adapter de parsing para páginas HTML **bem-comportadas e estáticas** onde o valor
não está num "artigo principal" em prosa (isso é o trafilatura, F1.4) nem exige um
navegador (Playwright, F1.3), mas na **estrutura do DOM**: links a seguir, listas
(vagas numa página de carreiras, cards de um diretório), e metadados (`<title>`,
`<meta>`, Open Graph). É o canivete de extração fina sobre um HTML já em mãos.

Lugar no F1:
- versus Firecrawl (F1.2) / trafilatura (F1.4): aqueles devolvem o **conteúdo
  editorial limpo**; o bs4 devolve **estrutura** — os `links` viram a fila do
  crawler Scrapy (F1.6) e o `select_text` por seletor (vagas/stack pública)
  alimenta a taxonomia de sinais AI-native (F1.11);
- versus Playwright (F1.3): não roda JS; consome o HTML cru — estático (via `fetch`)
  ou o já renderizado pelo F1.3 (`RenderedPage.html`). O roteador (F1.7) decide a
  origem.

Puro-Python, sem chave: o núcleo (`extract`/`extract_links`/`select_text`) é
testável **offline** sobre HTML fixo. Há um `fetch` de conveniência (GET via stdlib)
gated por rede nos testes, como os demais adapters; robots/rate limit/quota e o UA
definitivo entram na compliance (F1.8) — aqui o `fetch` já manda um UA identificável.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, NamedTuple
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

# User-agent identificável centralizado na compliance (F1.8) — fonte única do UA.
from .compliance import USER_AGENT as DEFAULT_USER_AGENT

# Backend de parsing: o `html.parser` da stdlib evita depender de lxml — o bs4 já
# normaliza HTML mal-formado por cima dele, que é o ganho deste adapter vs F1.3.
_PARSER = "html.parser"

# Tags cujo conteúdo textual nunca interessa (código/estilo/metadados).
_SKIP_TAGS = ["script", "style", "noscript", "template", "head", "svg", "iframe"]

# Esquemas de href que não são páginas a seguir (não viram link de crawl).
_NON_PAGE_SCHEMES = ("javascript:", "mailto:", "tel:", "data:")


class Link(NamedTuple):
    """Hyperlink já absolutizado + texto âncora — unidade de fila do crawler (F1.6)."""

    url: str
    text: str = ""


@dataclass(frozen=True)
class ParsedPage:
    """HTML simples já parseado em estrutura, pronto p/ crawl (F1.6) e sinais (F1.11).

    `text` é o texto visível (sem script/style); `links` são as âncoras absolutizadas
    e deduplicadas que alimentam a fila do crawler (F1.6); `metadata` agrega `<meta>`
    (name/property, incl. Open Graph) + `lang` p/ o enriquecimento de perfil (F2). A
    proveniência completa (hash + `fetched_at` na tabela `evidence`) é montada em F1.9
    a partir daqui.
    """

    url: str
    title: str = ""
    text: str = ""
    links: tuple[Link, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        """True se não sobrou texto nem links úteis (página vazia/bloqueada)."""
        return not self.text.strip() and not self.links


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, _PARSER)


def _clean(text: str) -> str:
    """Colapsa espaços horizontais e quebras redundantes, preservando parágrafos."""
    text = re.sub(r"[ \t\f\r]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _text_from_soup(soup: BeautifulSoup) -> str:
    """Texto visível: remove script/style/etc. e usa fronteiras de tag como quebra.

    Muta o soup (decompose) — por isso `extract` captura título/meta/links **antes**.
    """
    for tag in soup.find_all(_SKIP_TAGS):
        tag.decompose()
    return _clean(soup.get_text(separator="\n"))


def _meta_from_soup(soup: BeautifulSoup) -> dict[str, Any]:
    """Agrega `<meta name|property>` com `content` + o `lang` do `<html>`.

    Primeira ocorrência vence (`setdefault`) — páginas às vezes repetem `og:*`.
    """
    meta: dict[str, Any] = {}
    for tag in soup.find_all("meta"):
        key = tag.get("name") or tag.get("property")
        content = tag.get("content")
        if key and content:
            meta.setdefault(key, content)
    html_tag = soup.find("html")
    if html_tag is not None and html_tag.get("lang"):
        meta.setdefault("lang", html_tag["lang"])
    return meta


def _links_from_soup(
    soup: BeautifulSoup,
    *,
    base_url: str | None = None,
    same_domain: bool = False,
) -> tuple[Link, ...]:
    """Âncoras seguíveis: absolutizadas contra `base_url`, deduplicadas, na ordem do DOM.

    Pula `#`-âncoras e esquemas não-página (mailto/tel/javascript/data). `same_domain`
    mantém só links do mesmo host de `base_url` — usado pelo crawler (F1.6) p/ não
    sair do site da startup.
    """
    base = base_url or _base_href(soup)
    base_host = urlparse(base).netloc.lower() if base else ""
    out: list[Link] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or href.startswith("#") or href.lower().startswith(_NON_PAGE_SCHEMES):
            continue
        url = urljoin(base, href) if base else href
        if not urlparse(url).scheme.startswith("http"):
            continue
        if same_domain and base_host and urlparse(url).netloc.lower() != base_host:
            continue
        if url in seen:
            continue
        seen.add(url)
        out.append(Link(url=url, text=anchor.get_text(" ", strip=True)))
    return tuple(out)


def _base_href(soup: BeautifulSoup) -> str | None:
    """`<base href>` da página, quando declarado (tem prioridade na absolutização)."""
    base_tag = soup.find("base", href=True)
    return base_tag["href"].strip() if base_tag is not None else None


def extract(html: str, *, url: str = "", base_url: str | None = None) -> ParsedPage:
    """Parseia um HTML simples em estrutura (puro, testável offline).

    Recebe o HTML já em mãos — um GET estático (`fetch`) ou o `RenderedPage.html` do
    Playwright (F1.3). `base_url` (ou a própria `url`, ou um `<base href>`) absolutiza
    os links relativos. HTML vazio devolve `ParsedPage` vazio (`is_empty`), não erro —
    o roteador (F1.7) cai em outro adapter.
    """
    if not html.strip():
        return ParsedPage(url=url)
    soup = _soup(html)
    title = soup.title.get_text(strip=True) if soup.title else ""
    metadata = _meta_from_soup(soup)
    links = _links_from_soup(soup, base_url=base_url or url or None)
    text = _text_from_soup(soup)  # muta o soup: deixar por último
    return ParsedPage(url=url, title=title, text=text, links=links, metadata=metadata)


def extract_links(
    html: str,
    *,
    base_url: str | None = None,
    same_domain: bool = False,
) -> tuple[Link, ...]:
    """Só os links seguíveis de um HTML — atalho p/ alimentar a fila do crawler (F1.6)."""
    return _links_from_soup(_soup(html), base_url=base_url, same_domain=same_domain)


def select_text(html: str, selector: str) -> list[str]:
    """Texto dos elementos que casam um seletor CSS, na ordem do DOM (puro, offline).

    Extração dirigida p/ sinais estruturados (F1.11): ex. `select_text(html, "ul.jobs li")`
    pega os títulos de vaga de uma página de carreiras. Vazio quando nada casa.
    """
    return [el.get_text(" ", strip=True) for el in _soup(html).select(selector)]


def fetch(
    url: str,
    *,
    timeout: float = 30.0,
    user_agent: str | None = None,
) -> ParsedPage:
    """Baixa `url` (GET stdlib) e parseia — conveniência p/ página estática simples.

    Manda um UA identificável (compliance F1.8) e delega ao `extract`, usando a URL
    final (segue redirect) como base dos links. Para HTML que já temos (ex.: render do
    F1.3) use `extract` direto e evite uma segunda requisição.
    """
    if not url.strip():
        raise ValueError("url vazia")
    if not url.lower().startswith(("http://", "https://")):
        raise ValueError("url precisa ser http(s)")
    from urllib.request import Request, urlopen

    request = Request(url, headers={"User-Agent": user_agent or DEFAULT_USER_AGENT})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 (esquema validado acima)
        raw = response.read()
        final_url = response.geturl()
        charset = response.headers.get_content_charset() or "utf-8"
    html = raw.decode(charset, errors="replace")
    return extract(html, url=final_url, base_url=final_url)
