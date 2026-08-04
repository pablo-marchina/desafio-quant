import asyncio
import os
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from dotenv import load_dotenv
from fastapi import HTTPException
from tavily import TavilyClient

from app.schemas import (
    DiscoverSourcesRequest,
    DiscoverSourcesResponse,
    DiscoveredSource,
)


ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)


TRUSTED_NEWS_DOMAINS = {
    "startups.com.br",
    "startse.com",
    "exame.com",
    "braziljournal.com",
    "neofeed.com.br",
    "valor.globo.com",
    "pegng.globo.com",
    "mobiletime.com.br",
    "meioemensagem.com.br",
}

PUBLIC_ECOSYSTEM_DOMAINS = {
    "abstartups.com.br",
    "endeavor.org.br",
    "inovativabrasil.com.br",
    "100os.net",
    "distrito.me",
    "cubo.network",
    "ligaventures.com.br",
    "aceventures.com.br",
}


def normalize_url(url: str) -> str:
    parsed = urlparse(url)

    filtered_query = [
        (key, value)
        for key, value in parse_qsl(parsed.query)
        if not key.lower().startswith("utm_")
    ]

    path = parsed.path.rstrip("/") or "/"

    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc.lower(),
            path,
            "",
            urlencode(filtered_query),
            "",
        )
    )


def get_domain(url: str) -> str:
    domain = urlparse(url).netloc.lower()
    return domain.removeprefix("www.")


def is_same_domain(first_url: str, second_url: str) -> bool:
    return get_domain(first_url) == get_domain(second_url)


def is_domain_in_list(domain: str, allowed_domains: set[str]) -> bool:
    return any(
        domain == allowed_domain
        or domain.endswith(f".{allowed_domain}")
        for allowed_domain in allowed_domains
    )


def build_search_plan(
    startup_name: str,
    sector: str | None
) -> list[str]:
    sector_term = sector.strip() if sector else "startup"

    return [
        f'"{startup_name}" {sector_term} Brasil',
        f'"{startup_name}" inteligência artificial produto',
        f'"{startup_name}" captação investimento',
        f'"{startup_name}" site oficial',
    ]


def result_mentions_startup(
    title: str,
    snippet: str,
    startup_name: str
) -> bool:
    combined_text = f"{title} {snippet}".casefold()
    normalized_name = " ".join(startup_name.casefold().split())

    return normalized_name in combined_text


def classify_source(
    url: str,
    title: str,
    snippet: str,
    official_url: str | None
) -> tuple[str, int, int, str]:
    domain = get_domain(url)
    combined_text = f"{title} {snippet}".casefold()

    if official_url and is_same_domain(url, official_url):
        return (
            "official_site",
            1,
            100,
            "Fonte oficial informada manualmente pelo usuário."
        )

    if is_domain_in_list(domain, TRUSTED_NEWS_DOMAINS):
        return (
            "news",
            2,
            80,
            "Veículo público de notícias útil para contexto, funding ou tração."
        )

    if is_domain_in_list(domain, PUBLIC_ECOSYSTEM_DOMAINS):
        return (
            "public_ecosystem",
            3,
            65,
            "Fonte pública do ecossistema de startups; usada como apoio."
        )

    if any(
        keyword in combined_text
        for keyword in ["produto", "plataforma", "solução", "solucao", "carreiras"]
    ):
        return (
            "candidate_company_page",
            3,
            55,
            "Página pública candidata relacionada ao produto ou à empresa; precisa de validação posterior."
        )

    return (
        "public_web",
        3,
        40,
        "Fonte pública encontrada na busca; prioridade menor até validação."
    )


def run_tavily_search(
    client: TavilyClient,
    query: str
) -> list[dict]:
    response = client.search(
        query=query,
        search_depth="basic",
        max_results=4,
        topic="general",
        include_answer=False,
        include_raw_content=False,
    )

    return response.get("results", [])


async def discover_sources(
    payload: DiscoverSourcesRequest
) -> DiscoverSourcesResponse:
    api_key = os.getenv("TAVILY_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=503,
            detail=(
                "TAVILY_API_KEY não encontrada. "
                "Crie backend/.env e configure sua chave da Tavily."
            )
        )

    queries = build_search_plan(
        startup_name=payload.startup_name,
        sector=payload.sector,
    )

    client = TavilyClient(api_key=api_key)

    discovered_sources = []
    seen_urls = set()

    official_url = None

    if payload.official_url:
        official_url = normalize_url(str(payload.official_url))

        discovered_sources.append(
            DiscoveredSource(
                url=official_url,
                title="URL oficial informada",
                snippet=None,
                source_type="official_site",
                tier=1,
                priority=100,
                reason="URL oficial fornecida manualmente pelo usuário.",
                search_query=None,
            )
        )

        seen_urls.add(official_url)

    try:
        for query in queries:
            results = await asyncio.to_thread(
                run_tavily_search,
                client,
                query,
            )

            for result in results:
                raw_url = result.get("url")

                if not raw_url:
                    continue

                title = result.get("title") or "Título não disponível"
                snippet = str(result.get("content") or "")

                if not result_mentions_startup(
                    title=title,
                    snippet=snippet,
                    startup_name=payload.startup_name,
                ):
                    continue

                normalized_url = normalize_url(raw_url)

                if normalized_url in seen_urls:
                    continue

                source_type, tier, priority, reason = classify_source(
                    url=normalized_url,
                    title=title,
                    snippet=snippet,
                    official_url=official_url,
                )

                discovered_sources.append(
                    DiscoveredSource(
                        url=normalized_url,
                        title=title,
                        snippet=snippet[:500] if snippet else None,
                        source_type=source_type,
                        tier=tier,
                        priority=priority,
                        reason=reason,
                        search_query=query,
                    )
                )

                seen_urls.add(normalized_url)

    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=(
                "Falha ao consultar a API de busca pública. "
                f"Motivo: {type(error).__name__} - {str(error)}"
            )
        ) from error

    discovered_sources.sort(
        key=lambda source: (
            -source.priority,
            source.tier,
            source.title.casefold(),
        )
    )

    selected_sources = discovered_sources[:payload.max_sources]

    return DiscoverSourcesResponse(
        startup_name=payload.startup_name,
        queries_used=queries,
        sources=selected_sources,
        sources_found=len(selected_sources),
    )