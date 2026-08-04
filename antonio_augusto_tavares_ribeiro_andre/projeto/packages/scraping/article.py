"""Extração do texto principal de blogs/notícias via trafilatura (F1.4).

Adapter de extração focado em **conteúdo editorial** — artigos de imprensa de
tecnologia/startups (§9.2, `news.yaml`) e posts de blog — onde o sinal está no
corpo do texto e o ruído ao redor (nav, "leia também", share, comentários) é
grande. O trafilatura isola o **artigo principal** e ainda devolve metadados
editoriais (autor, data de publicação, veículo), valiosos para a proveniência de
notícia (F1.9) e para datar sinais no enriquecimento de perfil (F2).

Lugar no F1: diferente do Firecrawl (F1.2, API externa) e do Playwright (F1.3,
navegador headless), o trafilatura é **puro-Python, sem rede nem chave** — extrai
a partir de um HTML que já temos em mãos. O caso de uso principal é refinar o
`html` cru que o Playwright (F1.3) renderizou, quando o roteador (F1.7) decidir
que vale a pena; por isso o núcleo `extract` recebe HTML e é testável **offline**.
Há um `fetch` de conveniência que baixa a URL (rede) para páginas estáticas,
gated nos testes como os adapters reais (F1.1/F1.2). Robots/rate limit/quota e o
user-agent definitivo são formalizados na compliance (F1.8); aqui o `fetch` já
manda um UA identificável por padrão.
"""

from __future__ import annotations

from configparser import ConfigParser
from dataclasses import dataclass, field
from typing import Any

from trafilatura import bare_extraction, fetch_url
from trafilatura.settings import use_config

# User-agent identificável centralizado na compliance (F1.8) — fonte única do UA.
from .compliance import USER_AGENT as DEFAULT_USER_AGENT

# Campos do retorno do trafilatura que NÃO viram metadata: ou já são campo de
# primeira classe do `Article`, ou são objetos lxml/duplicatas não serializáveis
# (`body`/`commentsbody` são Elements; `raw_text` duplica `text`).
_DROP_FROM_META = frozenset(
    {"body", "commentsbody", "comments", "raw_text", "text", "title", "url"}
)


@dataclass(frozen=True)
class Article:
    """Artigo de blog/notícia já isolado do boilerplate, pronto para RAG e evidência.

    `text` é o corpo principal extraído (sem nav/rodapé/related). Os metadados
    editoriais ganham campos próprios por serem caros para a proveniência (F1.9) e
    o enriquecimento (F2): `author` e `date` datam/atribuem o sinal, `sitename` é o
    veículo. `metadata` carrega o resto do que o trafilatura devolveu, sem perda.
    A proveniência completa (hash + `fetched_at` na tabela `evidence`) é montada em
    F1.9 a partir daqui. `author` é tratado como dado profissional público (F1.13).
    """

    url: str
    text: str
    title: str = ""
    author: str = ""
    date: str = ""
    description: str = ""
    sitename: str = ""
    language: str = ""
    categories: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        """True se não sobrou texto de artigo útil (página não-editorial/bloqueada)."""
        return not self.text.strip()


def _parse(url: str | None, doc: dict[str, Any] | None) -> Article:
    """Converte o dict do `bare_extraction` em `Article` (puro, testável offline).

    `doc=None` é o caminho de "nada extraível" do trafilatura (HTML sem artigo,
    página bloqueada): vira um `Article` vazio (`is_empty`) em vez de erro, para o
    roteador (F1.7) poder cair em outro adapter. A `url` final do documento tem
    prioridade sobre a pedida (segue canonical/redirect quando o trafilatura resolve).
    """
    if not doc:
        return Article(url=url or "", text="")
    categories = doc.get("categories") or ()
    tags = doc.get("tags") or ()
    metadata = {
        k: v for k, v in doc.items() if k not in _DROP_FROM_META and v not in (None, "", [], ())
    }
    return Article(
        url=doc.get("url") or url or "",
        text=doc.get("text") or "",
        title=doc.get("title") or "",
        author=doc.get("author") or "",
        date=doc.get("date") or "",
        description=doc.get("description") or "",
        sitename=doc.get("sitename") or "",
        language=doc.get("language") or "",
        categories=tuple(categories),
        tags=tuple(tags),
        metadata=metadata,
    )


def extract(
    html: str,
    *,
    url: str | None = None,
    include_comments: bool = False,
    favor_precision: bool = False,
) -> Article:
    """Isola o artigo principal de um HTML de blog/notícia (puro, offline).

    Recebe o HTML já em mãos — tipicamente o `RenderedPage.html` do Playwright
    (F1.3) ou um GET estático — e devolve o corpo limpo + metadados editoriais.
    `include_comments=False` (default) mantém threads de comentário fora do corpo
    do artigo. `favor_precision=True` enviesa contra boilerplate (menos texto,
    menos ruído) — útil em portais com muito "leia também". HTML vazio ou sem
    artigo extraível devolve `Article` vazio (`is_empty`), não erro.
    """
    if not html.strip():
        return _parse(url, None)
    doc = bare_extraction(
        html,
        url=url,
        with_metadata=True,
        include_comments=include_comments,
        favor_precision=favor_precision,
    )
    return _parse(url, doc.as_dict() if doc is not None else None)


def _config(user_agent: str | None) -> ConfigParser:
    """Cópia do config default do trafilatura com nosso UA (sem mutar o global).

    O trafilatura lê o user-agent de `DEFAULT.USER_AGENTS`; `use_config()` devolve
    um config compartilhado, então copiamos a seção DEFAULT antes de sobrescrever
    para não vazar o UA para o resto do processo.
    """
    cfg = ConfigParser()
    cfg.read_dict({"DEFAULT": dict(use_config()["DEFAULT"])})
    cfg.set("DEFAULT", "USER_AGENTS", user_agent or DEFAULT_USER_AGENT)
    return cfg


def fetch(
    url: str,
    *,
    no_ssl: bool = False,
    user_agent: str | None = None,
    include_comments: bool = False,
    favor_precision: bool = False,
) -> Article:
    """Baixa `url` (rede) e extrai o artigo — conveniência para página estática.

    Manda um UA identificável (compliance F1.8) e delega a extração ao `extract`.
    Quando o download falha ou é bloqueado, o trafilatura devolve `None` e isto
    vira um `Article` vazio (`is_empty`) — o roteador (F1.7) cai para o Playwright
    (F1.3). Para HTML que já temos (ex.: render do F1.3), use `extract` direto e
    evite uma segunda requisição.
    """
    if not url.strip():
        raise ValueError("url vazia")
    downloaded = fetch_url(url, no_ssl=no_ssl, config=_config(user_agent))
    if downloaded is None:
        return _parse(url, None)
    return extract(
        downloaded,
        url=url,
        include_comments=include_comments,
        favor_precision=favor_precision,
    )
