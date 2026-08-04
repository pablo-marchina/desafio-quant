from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from app.collectors.url import CollectedSourceDocument, collect_url
from app.discovery.market import NewsArticle, crawl_market_articles


@dataclass(frozen=True)
class AnalysisContext:
    title: str | None
    text: str
    source_count: int
    source_urls: tuple[str, ...]
    official_document: CollectedSourceDocument | None


def build_analysis_context_from_url(
    url: str,
    title: str | None,
    user_agent: str,
    client: httpx.Client | None = None,
) -> AnalysisContext:
    official_document = collect_url(url, user_agent, client=client)
    official_text = official_document.extracted_text or ""
    normalized_url = official_document.url
    context_title = title or official_document.title or _name_from_url(normalized_url)
    related_articles = _collect_related_articles(context_title, normalized_url, client)
    context_text = _compose_context_text(
        company_name=context_title,
        url=normalized_url,
        official_text=official_text,
        related_articles=related_articles,
    )
    source_urls = tuple(
        dict.fromkeys(
            [official_document.url]
            + [article.url for article in related_articles if article.url]
        )
    )

    return AnalysisContext(
        title=context_title,
        text=context_text,
        source_count=len(source_urls),
        source_urls=source_urls,
        official_document=official_document,
    )


def _collect_related_articles(
    company_name: str | None,
    url: str,
    client: httpx.Client | None,
) -> tuple[NewsArticle, ...]:
    name = (company_name or _name_from_url(url) or "").strip()
    if not name:
        return ()

    domain = _domain_from_url(url)
    queries = (
        f'"{name}" startup IA',
        f'"{name}" inteligência artificial',
        f'"{name}" LLM agentes IA',
        f'"{name}" {domain} IA',
    )
    return crawl_market_articles(queries, client=client, per_query_limit=4)[:10]


def _compose_context_text(
    company_name: str | None,
    url: str,
    official_text: str,
    related_articles: tuple[NewsArticle, ...],
) -> str:
    article_lines = [
        (
            f"- {article.title} | fonte: {article.source} | "
            f"data: {_article_date(article)} | "
            f"url: {article.url}"
        )
        for article in related_articles
    ]
    sections = [
        "Contexto consolidado para análise NVIDIA.",
        f"Empresa: {company_name or 'não informada'}",
        f"URL oficial: {url}",
        "",
        "Fonte oficial coletada:",
        official_text[:7000] or "A coleta da fonte oficial não retornou texto útil.",
    ]
    if article_lines:
        sections.extend(
            [
                "",
                "Evidências externas recentes encontradas em notícias:",
                *article_lines,
            ]
        )
    else:
        sections.extend(
            [
                "",
                "Evidências externas recentes: nenhuma notícia adicional foi encontrada.",
            ]
        )
    return "\n".join(sections)


def _name_from_url(url: str) -> str | None:
    domain = _domain_from_url(url)
    if not domain:
        return None
    return domain.split(".", 1)[0].replace("-", " ").title()


def _domain_from_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.replace("www.", "")


def _article_date(article: NewsArticle) -> str:
    if not article.published_at:
        return "sem data"
    return article.published_at.date().isoformat()
