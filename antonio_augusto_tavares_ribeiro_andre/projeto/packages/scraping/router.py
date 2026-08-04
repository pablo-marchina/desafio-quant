"""Roteador de fetch: estático vs dinâmico, escolhe o adapter certo (F1.7).

Os adapters F1.2–F1.5 sabem extrair **uma** página; nenhum sabe *qual* usar. Este é o
maestro: dada uma URL e um **intent** de conteúdo, tenta o caminho **estático** (barato)
primeiro e só **cai para o dinâmico** (Playwright, F1.3 — caro, headless) quando o
estático volta vazio/raso — o sinal típico de página dependente de JS. Devolve um
resultado unificado (`FetchResult`) com o texto principal, o html quando renderizado e
**qual estratégia** o produziu (rastreável p/ a proveniência F1.9).

Intent → adapter (o caller decide o intent a partir da fonte §9: `news`→article,
`directory`/carreiras→structured, demais→clean):
- **clean** (default, p/ RAG): estático = Firecrawl (F1.2, conteúdo principal limpo);
  dinâmico = render (F1.3) refinado pelo trafilatura (F1.4) sobre o html renderizado.
- **article** (§9.2 notícias/blog): estático = trafilatura (F1.4); dinâmico = render +
  trafilatura sobre o html.
- **structured** (diretórios/carreiras, links/meta): estático = BeautifulSoup (F1.5);
  dinâmico = render + bs4 sobre o html.

O **núcleo de decisão é puro e testável offline**: `is_insufficient` (gatilho do
fallback dinâmico) e `extract_rendered` (re-extração do html já renderizado via
trafilatura/bs4, ambos puros) não tocam a rede. Os adapters de rede (Firecrawl,
Playwright) são importados de forma preguiçosa e podem ser **injetados** em `fetch`
(`scrape=`/`render=`) p/ exercitar a lógica de fallback sem rede/chave. Compliance
(robots/rate limit/UA) e quota de free tier são responsabilidade dos adapters/F1.8;
aqui é só roteamento.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from .article import Article
    from .dynamic import RenderedPage
    from .firecrawl import ExtractedPage
    from .soup import ParsedPage

# Intent de conteúdo → seleciona o extrator. Vem do caller (tipo da fonte §9).
ContentKind = Literal["clean", "article", "structured"]

# Abaixo deste tanto de texto útil, suspeita-se de página dependente de JS (casca
# servida sem conteúdo) → vale o custo de renderizar no Playwright (F1.3).
DEFAULT_MIN_CHARS = 200

# Adapters de rede injetáveis (default = os reais, importados preguiçosamente).
ScrapeFn = Callable[[str], "ExtractedPage"]
RenderFn = Callable[[str], "RenderedPage"]


@dataclass(frozen=True)
class FetchResult:
    """Resultado unificado do roteador, pronto p/ virar evidência (F1.9) e RAG (F3).

    `text` é o conteúdo principal (markdown do Firecrawl, corpo do trafilatura ou
    texto visível do bs4/render, conforme o intent). `html` carrega o DOM quando o
    caminho dinâmico rodou (p/ re-extração futura). `strategy` registra a cadeia de
    adapters que produziu isto (ex.: `"firecrawl"`, `"playwright+trafilatura"`) — é o
    que torna a escolha do roteador auditável na proveniência (F1.9).
    """

    url: str
    text: str
    html: str = ""
    title: str = ""
    strategy: str = ""
    rendered: bool = False
    status_code: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        """True se o roteador não conseguiu texto útil por nenhum caminho."""
        return not self.text.strip()


def is_insufficient(text: str, *, min_chars: int = DEFAULT_MIN_CHARS) -> bool:
    """True se o texto estático é raso demais p/ confiar (gatilho do render, F1.3)."""
    return len(text.strip()) < min_chars


def _from_extracted(page: ExtractedPage) -> FetchResult:
    """Firecrawl (F1.2) → resultado unificado (caminho estático do intent `clean`)."""
    return FetchResult(
        url=page.url,
        text=page.markdown,
        title=page.title,
        strategy="firecrawl",
        status_code=page.status_code,
        metadata=dict(page.metadata),
    )


def _from_article(
    article: Article,
    *,
    html: str = "",
    status_code: int | None = None,
    strategy: str = "trafilatura",
    rendered: bool = False,
) -> FetchResult:
    """trafilatura (F1.4) → resultado unificado (estático `article` ou pós-render)."""
    return FetchResult(
        url=article.url,
        text=article.text,
        html=html,
        title=article.title,
        strategy=strategy,
        rendered=rendered,
        status_code=status_code,
        metadata=dict(article.metadata),
    )


def _from_parsed(
    parsed: ParsedPage,
    *,
    html: str = "",
    status_code: int | None = None,
    strategy: str = "soup",
    rendered: bool = False,
) -> FetchResult:
    """BeautifulSoup (F1.5) → resultado unificado (estático `structured` ou pós-render)."""
    return FetchResult(
        url=parsed.url,
        text=parsed.text,
        html=html,
        title=parsed.title,
        strategy=strategy,
        rendered=rendered,
        status_code=status_code,
        metadata=dict(parsed.metadata),
    )


def extract_rendered(intent: ContentKind, rendered: RenderedPage) -> FetchResult:
    """Re-extrai o conteúdo do html já renderizado (F1.3) conforme o intent (puro, offline).

    `structured` aplica o bs4 (F1.5) — links/meta do DOM; `clean`/`article` aplicam o
    trafilatura (F1.4) p/ isolar o conteúdo principal. Se o trafilatura não achar
    artigo, cai no texto visível básico que o próprio render (F1.3) já produziu — é o
    melhor esforço, não erro. Opera sobre um `RenderedPage` já em mãos, então é
    testável sem navegador nem rede.
    """
    if intent == "structured":
        from .soup import extract as parse_html

        parsed = parse_html(rendered.html, url=rendered.url)
        return _from_parsed(
            parsed,
            html=rendered.html,
            status_code=rendered.status_code,
            strategy="playwright+soup",
            rendered=True,
        )

    from .article import extract as extract_article

    article = extract_article(rendered.html, url=rendered.url)
    if not article.is_empty:
        return _from_article(
            article,
            html=rendered.html,
            status_code=rendered.status_code,
            strategy="playwright+trafilatura",
            rendered=True,
        )
    # trafilatura não isolou artigo → texto visível básico do render (F1.3).
    return FetchResult(
        url=rendered.url,
        text=rendered.text,
        html=rendered.html,
        title=rendered.title,
        strategy="playwright",
        rendered=True,
        status_code=rendered.status_code,
        metadata=dict(rendered.metadata),
    )


def _real_scrape(url: str) -> ExtractedPage:
    from .firecrawl import scrape

    return scrape(url)


def _real_render(url: str) -> RenderedPage:
    from .dynamic import render

    return render(url)


def _static(url: str, intent: ContentKind, *, scrape: ScrapeFn | None) -> FetchResult:
    """Caminho estático (barato) conforme o intent — sem render."""
    if intent == "clean":
        return _from_extracted((scrape or _real_scrape)(url))
    if intent == "article":
        from .article import fetch as fetch_article

        return _from_article(fetch_article(url))
    from .soup import fetch as fetch_html

    return _from_parsed(fetch_html(url))


def fetch(
    url: str,
    *,
    intent: ContentKind = "clean",
    min_chars: int = DEFAULT_MIN_CHARS,
    force_render: bool = False,
    scrape: ScrapeFn | None = None,
    render: RenderFn | None = None,
) -> FetchResult:
    """Busca `url` escolhendo estático vs dinâmico e devolve o resultado unificado (F1.7).

    Tenta o caminho estático do `intent`; se o texto vier raso (`is_insufficient`,
    sinal de JS), **cai para o render** (Playwright, F1.3) e re-extrai conforme o
    intent. `force_render=True` pula direto p/ o dinâmico (fonte sabidamente JS).
    `scrape`/`render` permitem injetar adapters (teste/uso custom) — default são os
    reais. Se o render falhar mas o estático ao menos trouxe algo, devolve o estático.
    O resultado pode vir `is_empty` (nenhum caminho rendeu) — não é erro; o caller
    decide.
    """
    if not url.strip():
        raise ValueError("url vazia")

    static: FetchResult | None = None
    static_error: Exception | None = None
    if not force_render:
        # O caminho estático pode **falhar duro** (ex.: Firecrawl sem crédito/quota → `PaymentRequired`,
        # ou rede). Em vez de abortar a coleta, cai p/ o render (Playwright, F1.3, **grátis e local**) —
        # que ainda renderiza sites JS. Sem este catch, um site `clean` (oficial) com o Firecrawl
        # esgotado rendia 0 docs → perfil vazio → classe/AIMI falsos (rivio.ai, 2026-06-23).
        try:
            static = _static(url, intent, scrape=scrape)
        except Exception as exc:  # noqa: BLE001 — qualquer falha do estático tenta o render
            static_error = exc
        if static is not None and not is_insufficient(static.text, min_chars=min_chars):
            return static

    rendered_page = (render or _real_render)(url)
    result = extract_rendered(intent, rendered_page)
    if result.is_empty and static is not None and not static.is_empty:
        return static  # render não rendeu; fica com o pouco que o estático trouxe
    if result.is_empty and static is None and static_error is not None:
        raise static_error  # nem estático nem render renderam → propaga o erro original (rastreável)
    return result
