"""Crawler de varredura em escala via Scrapy (F1.6).

Onde os adapters anteriores (F1.2–F1.5) extraem **uma** página dada a URL, este é o
estágio que **descobre URLs em escala**: parte das seeds coletáveis (§9, F0.9), varre
as páginas de listagem/portfólio (programas, aceleradoras, canais oficiais) seguindo
links **dentro do mesmo domínio** e devolve, por página visitada, o texto + os links
de saída. Esses links de saída são a matéria-prima da **fila de empresas candidatas**
do cohort builder (F1.14): de um portfólio de aceleradora saem dezenas de domínios de
startup a perfilar.

Lugar no F1 e nas decisões travadas:
- **Compliance (F1.8):** roda com `ROBOTSTXT_OBEY=True`, `DOWNLOAD_DELAY`/autothrottle
  (rate limit) e o mesmo user-agent identificável dos demais adapters. A varredura é
  confinada ao(s) host(s) das seeds (não sai pulando a web).
- **ToS por fonte (F1.15):** o crawler **só** parte de fontes `collectable` (policy
  `allow`). As plataformas proprietárias do §9.1 (`directory`, quase todas `api_only`/
  `deny`) **não** são varridas direto — entram como descoberta via API/parceria. Quem
  alimenta o crawler de fato são os `program`/`news` `allow` (portfólios públicos,
  canais oficiais). `collectable_seeds` faz esse filtro e registra o que pulou.
- **versus F1.5 (BeautifulSoup):** o parsing de cada página reusa o `extract` do bs4
  (título/texto/links/meta); o crawler acrescenta a **máquina de varredura** (fila,
  same-domain, profundidade, limite de páginas, robots) que o adapter de página única
  não tem.

O núcleo é testável **offline**: `collectable_seeds` (gate F1.15) e `parse_response`
(parsing + decisão de quais links seguir) não dependem do Scrapy. O `scrapy` é
importado de forma preguiçosa só em `_build_spider`/`crawl`, espelhando o import
preguiçoso de Playwright (F1.3) e Firecrawl (F1.2) — assim `import packages.scraping`
e o núcleo puro não arrastam o Twisted. Atenção: `crawl` sobe o reactor do Twisted
(bloqueante, um por processo); alvo é o worker RQ (F2)/o cohort builder em lote (F1.14).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from .compliance import USER_AGENT as DEFAULT_USER_AGENT
from .soup import Link
from .soup import extract as parse_html

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .seeds import Source

@dataclass(frozen=True)
class CrawledPage:
    """Uma página visitada na varredura, com os links de saída p/ a fila (F1.14).

    `links` são **todas** as âncoras seguíveis da página (deduplicadas e absolutizadas
    pelo bs4, F1.5), inclusive externas — é delas que o cohort builder (F1.14) extrai os
    domínios de startup candidatos. `depth` é a distância em saltos da seed; `source_id`
    amarra a página à fonte §9 que a originou (proveniência, F1.9). A proveniência
    completa (hash + `fetched_at` na tabela `evidence`) é montada em F1.9 a partir daqui.
    """

    url: str
    status_code: int | None = None
    depth: int = 0
    title: str = ""
    text: str = ""
    links: tuple[Link, ...] = ()
    source_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        """True se a página não rendeu texto nem links úteis (vazia/bloqueada)."""
        return not self.text.strip() and not self.links


@dataclass(frozen=True)
class CrawlPlan:
    """Plano de varredura derivado das seeds, já filtrado pela política (F1.15).

    `start_urls`/`allowed_domains` só contêm fontes coletáveis (`policy: allow`);
    `skipped` lista os ids das fontes barradas pela política de ToS (api_only/deny) —
    registrado para a varredura ser auditável, não silenciosa.
    """

    start_urls: tuple[str, ...]
    allowed_domains: tuple[str, ...]
    skipped: tuple[str, ...] = ()


def _host(url: str) -> str:
    """Host (netloc) em minúsculas de uma URL; vazio se não der p/ parsear."""
    return urlparse(url).netloc.lower()


def _host_allowed(host: str, allowed_hosts: Sequence[str]) -> bool:
    """True se `host` é um dos hosts permitidos ou um subdomínio dele.

    Sem `allowed_hosts` nada é seguido (varredura precisa de um escopo de domínio
    explícito — evita o crawler vazar para a web inteira).
    """
    if not host or not allowed_hosts:
        return False
    return any(host == a or host.endswith("." + a) for a in allowed_hosts)


def collectable_seeds(sources: Sequence[Source]) -> CrawlPlan:
    """Monta o plano de varredura a partir das seeds, aplicando o gate de ToS (F1.15).

    Só fontes `collectable` (policy `allow`) viram `start_urls`/`allowed_domains`; as
    demais (§9.1 proprietárias `api_only`/`deny`) vão para `skipped`. Domínios são
    deduplicados preservando a ordem das seeds.
    """
    start: list[str] = []
    domains: list[str] = []
    skipped: list[str] = []
    for src in sources:
        if not src.collectable:
            skipped.append(src.id)
            continue
        start.append(src.url)
        host = _host(src.url)
        if host and host not in domains:
            domains.append(host)
    return CrawlPlan(tuple(start), tuple(domains), tuple(skipped))


def parse_response(
    *,
    url: str,
    html: str,
    allowed_hosts: Sequence[str],
    status_code: int | None = None,
    depth: int = 0,
    source_id: str = "",
) -> tuple[CrawledPage, tuple[str, ...]]:
    """Transforma a resposta de uma página em `CrawledPage` + URLs a seguir (puro, offline).

    Reusa o `extract` do bs4 (F1.5) para título/texto/links/meta. A `CrawledPage`
    guarda **todas** as âncoras (inclusive externas, p/ a fila do F1.14); as URLs a
    seguir são só as que caem nos `allowed_hosts` (confinamento same-domain da
    varredura, F1.8). É a lógica que o spider do Scrapy chama por página — separada
    dele para ser testável sem reactor nem rede.
    """
    page = parse_html(html, url=url)
    follow = tuple(link.url for link in page.links if _host_allowed(_host(link.url), allowed_hosts))
    crawled = CrawledPage(
        url=page.url or url,
        status_code=status_code,
        depth=depth,
        title=page.title,
        text=page.text,
        links=page.links,
        source_id=source_id,
        metadata=page.metadata,
    )
    return crawled, follow


def _build_spider(
    *,
    start_urls: Sequence[str],
    allowed_domains: Sequence[str],
    source_by_host: dict[str, str],
    sink: list[CrawledPage],
    max_pages: int,
    max_depth: int,
    download_delay: float,
    user_agent: str,
) -> type:
    """Constrói a classe de Spider do Scrapy (import preguiçoso) ligada a este run.

    O parsing por página delega a `parse_response`; cada `CrawledPage` é anexada ao
    `sink` (a saída do run). Os `custom_settings` carregam a compliance (F1.8):
    obedecer robots, atrasar requisições/autothrottle, UA identificável, e os limites
    de profundidade/quantidade de páginas que evitam varredura sem fim.
    """
    import scrapy

    allowed_hosts = tuple(allowed_domains)

    class _DirectorySpider(scrapy.Spider):
        name = "tapi-directory"

        custom_settings = {
            "USER_AGENT": user_agent,
            "ROBOTSTXT_OBEY": True,  # F1.8: respeita robots.txt
            "DOWNLOAD_DELAY": download_delay,  # F1.8: rate limit por domínio
            "AUTOTHROTTLE_ENABLED": True,
            "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
            "DEPTH_LIMIT": max_depth,
            "CLOSESPIDER_PAGECOUNT": max_pages,
            "TELNETCONSOLE_ENABLED": False,
            "LOG_LEVEL": "ERROR",
        }

        def start_requests(self):  # noqa: ANN201 (assinatura do Scrapy)
            for url in start_urls:
                yield scrapy.Request(url, callback=self.parse, meta={"depth": 0})

        def parse(self, response):  # noqa: ANN001, ANN201 (assinatura do Scrapy)
            depth = response.meta.get("depth", 0)
            source_id = source_by_host.get(_host(response.url), "")
            page, follow = parse_response(
                url=response.url,
                html=response.text,
                allowed_hosts=allowed_hosts,
                status_code=response.status,
                depth=depth,
                source_id=source_id,
            )
            sink.append(page)
            if len(sink) >= max_pages or depth >= max_depth:
                return
            for next_url in follow:
                yield response.follow(next_url, callback=self.parse, meta={"depth": depth + 1})

    _DirectorySpider.allowed_domains = list(allowed_domains)
    return _DirectorySpider


def crawl(
    sources: Sequence[Source],
    *,
    max_pages: int = 50,
    max_depth: int = 2,
    download_delay: float = 1.0,
    user_agent: str | None = None,
) -> tuple[CrawledPage, ...]:
    """Varre as fontes coletáveis em escala e devolve as páginas visitadas (F1.6).

    Aplica o gate de ToS (F1.15) via `collectable_seeds` — fontes não-coletáveis são
    ignoradas (e não há erro se *alguma* for coletável). `max_pages`/`max_depth`
    limitam a varredura; `download_delay` é o rate limit por domínio (F1.8). Sobe o
    reactor do Twisted (bloqueante, **um por processo**) — alvo é o worker/cohort
    builder em lote (F1.14), não um loop asyncio. Levanta `ValueError` se nenhuma
    fonte for coletável.
    """
    plan = collectable_seeds(sources)
    if not plan.start_urls:
        raise ValueError(
            f"nenhuma fonte coletável (F1.15) entre {[s.id for s in sources]} — "
            f"puladas: {list(plan.skipped)}"
        )
    source_by_host = {_host(s.url): s.id for s in sources if s.collectable}
    sink: list[CrawledPage] = []
    spider = _build_spider(
        start_urls=plan.start_urls,
        allowed_domains=plan.allowed_domains,
        source_by_host=source_by_host,
        sink=sink,
        max_pages=max_pages,
        max_depth=max_depth,
        download_delay=download_delay,
        user_agent=user_agent or DEFAULT_USER_AGENT,
    )

    from scrapy.crawler import CrawlerProcess

    process = CrawlerProcess(settings={"LOG_LEVEL": "ERROR", "TELNETCONSOLE_ENABLED": False})
    process.crawl(spider)
    process.start()  # bloqueia até a varredura terminar; encerra o reactor
    return tuple(sink)
