"""
Researcher agent: multi-source URL discovery for Brazilian AI startups.
Strategy: probe known URL patterns first (fast), then DDG searches (broad).
"""

import asyncio
import httpx
from ddgs import DDGS


_SKIP_ALWAYS = [
    "youtube.com", "facebook.com", "twitter.com", "x.com",
    "instagram.com", "glassdoor.com", "google.com", "bing.com",
    "yahoo.com", "reddit.com", "wikipedia.org", "indeed.com",
    "jobs.lever.co", "greenhouse.io",
]

_PRIORITY_DOMAINS = [
    "crunchbase.com", "linkedin.com", "github.com",
    "startups.com.br", "abstartups.com.br", "anjos.co",
    "wellfound.com", "producthunt.com", "pitchbook.com",
]


def _domain(url: str) -> str:
    try:
        return url.split("/")[2]
    except Exception:
        return url


async def _probe_urls_async(urls: list[str]) -> list[str]:
    """HEAD-check candidate URLs — keeps only live ones."""
    async with httpx.AsyncClient(timeout=6, follow_redirects=True) as client:
        async def check(url: str) -> str | None:
            try:
                r = await client.head(url, headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code < 400:
                    return str(r.url)
            except Exception:
                pass
            return None

        results = await asyncio.gather(*[check(u) for u in urls])
    return [r for r in results if r]


async def _ddg_search_async(queries: list[str], max_per_query: int = 5) -> list[str]:
    seen_domains: set[str] = set()

    def run_ddg() -> list[str]:
        found: list[str] = []
        with DDGS() as ddgs:
            for query in queries:
                try:
                    for r in ddgs.text(query, max_results=max_per_query):
                        url = r.get("href", "")
                        if not url or any(s in url for s in _SKIP_ALWAYS):
                            continue
                        d = _domain(url)
                        if d not in seen_domains:
                            seen_domains.add(d)
                            found.append(url)
                except Exception:
                    continue
        return found

    return await asyncio.to_thread(run_ddg)


async def _research_async(name: str) -> list[str]:
    slug  = name.lower().replace(" ", "-")
    slug2 = name.lower().replace(" ", "")

    # 1. Probe high-value known-pattern URLs directly
    probes = [
        f"https://github.com/{slug}",
        f"https://github.com/{slug2}",
        f"https://www.crunchbase.com/organization/{slug}",
        f"https://www.crunchbase.com/organization/{slug2}",
        f"https://linkedin.com/company/{slug}",
        f"https://linkedin.com/company/{slug2}",
        f"https://www.producthunt.com/products/{slug}",
        f"https://wellfound.com/company/{slug}",
        f"https://startups.com.br/startups/{slug}",
        f"https://startups.com.br/startups/{slug2}",
    ]
    probed_task = asyncio.create_task(_probe_urls_async(probes))

    # 2. DDG broad search — 8 queries covering multiple angles
    queries = [
        f'"{name}" startup Brasil',
        f'"{name}" IA inteligência artificial tecnologia',
        f'"{name}" funding investimento seed série',
        f'"{name}" github tecnologia',
        f'"{name}" crunchbase',
        f'"{name}" linkedin empresa',
        f'"{name}" site:startupi.com.br OR site:startups.com.br OR site:abstartups.com.br',
        f'"{name}" TechCrunch OR Exame OR NeoFeed OR InfoMoney OR Época Negócios',
    ]
    ddg_task = asyncio.create_task(_ddg_search_async(queries))

    probed, ddg_urls = await asyncio.gather(probed_task, ddg_task)

    # 3. Merge: priority domains first, then rest, dedup by domain
    seen: set[str] = set()
    result: list[str] = []

    all_urls = probed + ddg_urls
    priority = [u for u in all_urls if any(p in u for p in _PRIORITY_DOMAINS)]
    rest     = [u for u in all_urls if u not in priority]

    for url in priority + rest:
        d = _domain(url)
        if d not in seen:
            seen.add(d)
            result.append(url)
        if len(result) >= 14:
            break

    print(f"[researcher] {len(result)} URLs para '{name}'")
    return result


def research_startup(name: str) -> list[str]:
    return asyncio.run(_research_async(name))


if __name__ == "__main__":
    import sys
    name = sys.argv[1] if len(sys.argv) > 1 else "Neoway"
    urls = asyncio.run(_research_async(name))
    for u in urls:
        print(u)
