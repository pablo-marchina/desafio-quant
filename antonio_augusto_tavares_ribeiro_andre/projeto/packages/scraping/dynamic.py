"""Renderização de páginas dinâmicas via Playwright (F1.3).

Adapter de extração para sites que **dependem de JavaScript** — SPAs (React/Vue),
conteúdo carregado por fetch/XHR, paywalls leves de JS — onde o Firecrawl (F1.2) ou
um GET estático devolvem casca vazia. Sobe um Chromium headless, deixa o JS rodar e
devolve o **DOM já renderizado** (`html`) + um texto visível limpo (`text`), pronto
para virar evidência rastreável (F1.9) e alimentar chunking/RAG (F3).

Divisão de trabalho no F1: este adapter só **renderiza**. A extração de conteúdo
principal mais fina (trafilatura F1.4 / BeautifulSoup F1.5) consome o `html` daqui
quando o roteador (F1.7) decidir que vale a pena; o `text` deste módulo é a extração
"básica" suficiente para RAG (tira script/style, preserva quebras de parágrafo). O
roteador (F1.7) é quem escolhe estático (Firecrawl) vs dinâmico (Playwright); robots/
rate limit/quota e o user-agent definitivo são formalizados na compliance (F1.8) —
aqui já mandamos um UA identificável por padrão.

O parsing (`extract_text`/`_parse`) é puro e testável **offline**, sem navegador nem
rede — espelha os adapters de busca (F1.1) e Firecrawl (F1.2). O `playwright` é
importado de forma preguiçosa dentro de `render`. Atenção: usa a API **síncrona** do
Playwright (alvo: worker RQ, F2); não pode ser chamado de dentro de um loop asyncio.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any, Literal

# User-agent identificável centralizado na compliance (F1.8) — fonte única do UA.
from .compliance import USER_AGENT as DEFAULT_USER_AGENT

# Quando o Playwright considera a navegação "pronta". `networkidle` espera a rede
# acalmar (bom p/ SPA que busca dados); `load`/`domcontentloaded` são mais rápidos.
WaitUntil = Literal["load", "domcontentloaded", "networkidle", "commit"]

# Tags cujo conteúdo textual nunca interessa (código/estilo/metadados).
_SKIP_TAGS = frozenset({"script", "style", "noscript", "template", "head", "svg", "iframe"})
# Tags de bloco: marcam fronteira de parágrafo p/ o texto não virar uma linha só.
_BLOCK_TAGS = frozenset(
    {
        "p",
        "div",
        "br",
        "li",
        "ul",
        "ol",
        "tr",
        "table",
        "section",
        "article",
        "header",
        "footer",
        "nav",
        "main",
        "aside",
        "figure",
        "figcaption",
        "blockquote",
        "pre",
        "hr",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
    }
)


@dataclass(frozen=True)
class RenderedPage:
    """Página dinâmica já renderizada (pós-JS), pronta p/ extração fina e evidência.

    `html` é o DOM serializado **depois** do JS rodar (o diferencial vs F1.2/estático);
    `text` é a extração de texto visível básica (script/style fora, parágrafos
    preservados) suficiente p/ RAG. `metadata` carrega o que mais for útil ao
    enriquecimento de perfil (F2). A proveniência completa (hash + `fetched_at` na
    tabela `evidence`) é montada em F1.9 a partir daqui.
    """

    url: str
    html: str
    text: str
    title: str = ""
    status_code: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        """True se a renderização não rendeu texto útil (página vazia/bloqueada)."""
        return not self.text.strip()


class _TextExtractor(HTMLParser):
    """Coleta texto visível do HTML, pulando script/style e marcando blocos.

    Usa só o `html.parser` da stdlib (sem bs4 — isso é F1.5) para manter o parsing
    puro e sem dependência. `convert_charrefs=True` já decodifica entidades (`&amp;`).
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip = 0
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in _SKIP_TAGS:
            self._skip += 1
        elif tag in _BLOCK_TAGS:
            self._buf.append("\n")

    def handle_startendtag(self, tag: str, attrs: Any) -> None:
        if tag in _BLOCK_TAGS:  # ex.: <br/>
            self._buf.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS:
            if self._skip:
                self._skip -= 1
        elif tag in _BLOCK_TAGS:
            self._buf.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip == 0:
            self._buf.append(data)

    @property
    def text(self) -> str:
        return "".join(self._buf)


def _clean(text: str) -> str:
    """Colapsa espaços horizontais e quebras redundantes, preservando parágrafos."""
    text = re.sub(r"[ \t\f\r]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text(html: str) -> str:
    """Extrai texto visível de um HTML renderizado (puro, testável offline).

    Remove conteúdo de script/style/etc. e insere quebras nas fronteiras de bloco
    para o texto ficar legível p/ chunking/RAG. Extração de conteúdo principal mais
    sofisticada fica para os adapters trafilatura (F1.4) / BeautifulSoup (F1.5).
    """
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    return _clean(parser.text)


def _parse(
    url: str,
    html: str,
    *,
    title: str = "",
    status_code: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> RenderedPage:
    """Monta o `RenderedPage` a partir do HTML renderizado (puro, sem navegador)."""
    return RenderedPage(
        url=url,
        html=html,
        text=extract_text(html),
        title=title,
        status_code=status_code,
        metadata=metadata or {},
    )


def render(
    url: str,
    *,
    wait_until: WaitUntil = "networkidle",
    timeout_ms: int = 30_000,
    wait_for_selector: str | None = None,
    user_agent: str | None = None,
) -> RenderedPage:
    """Renderiza `url` num Chromium headless (deixa o JS rodar) e devolve o DOM + texto.

    `wait_until` controla o critério de "pronto" (`networkidle` é o default seguro p/
    SPA); `wait_for_selector`, quando dado, espera um elemento específico aparecer
    (útil p/ conteúdo que chega tarde via fetch). `timeout_ms` limita tanto a
    navegação quanto a espera pelo seletor. `user_agent` sobrescreve o UA identificável
    padrão (compliance F1.8). O resultado pode vir vazio (`RenderedPage.is_empty`) se a
    página bloquear o bot.
    """
    if not url.strip():
        raise ValueError("url vazia")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        # `--no-sandbox`: o chromium recusa rodar como root (worker no Docker) sem isto;
        # `--disable-dev-shm-usage`: o `/dev/shm` pequeno do container crasha o chromium em páginas
        # grandes. Inócuos no host (user). Necessários p/ o render rodar no worker (fallback do
        # Firecrawl, 2026-06-23).
        browser = pw.chromium.launch(
            headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        try:
            context = browser.new_context(user_agent=user_agent or DEFAULT_USER_AGENT)
            page = context.new_page()
            response = page.goto(url, wait_until=wait_until, timeout=timeout_ms)
            if wait_for_selector:
                page.wait_for_selector(wait_for_selector, timeout=timeout_ms)
            html = page.content()
            title = page.title()
            final_url = page.url
            status = response.status if response is not None else None
        finally:
            browser.close()

    return _parse(final_url or url, html, title=title, status_code=status)
