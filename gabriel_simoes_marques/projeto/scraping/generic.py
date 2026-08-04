"""
Scraper: parallel async fetching with GitHub API + Playwright JS fallback.
"""

import asyncio
import json
import httpx
import trafilatura
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

_JS_REQUIRED = [
    "crunchbase.com", "linkedin.com", "wellfound.com", "producthunt.com",
]


# ── GitHub API ────────────────────────────────────────────────────────────────

async def _scrape_github(url: str, client: httpx.AsyncClient) -> dict | None:
    path = urlparse(url).path.strip("/").split("/")
    if not path or not path[0]:
        return None
    org = path[0]

    data = None
    ep = None
    for candidate in [f"orgs/{org}", f"users/{org}"]:
        try:
            r = await client.get(
                f"https://api.github.com/{candidate}",
                headers={"Accept": "application/vnd.github+json"},
            )
            if r.status_code == 200:
                data = r.json()
                ep = candidate
                break
        except Exception:
            pass
    if not data or not ep:
        return None

    repos_text = ""
    try:
        r = await client.get(
            f"https://api.github.com/{ep}/repos",
            params={"sort": "stars", "per_page": 8},
            headers={"Accept": "application/vnd.github+json"},
        )
        if r.status_code == 200:
            lines = []
            for repo in r.json()[:8]:
                if not isinstance(repo, dict):
                    continue
                topics = ", ".join(repo.get("topics", []))
                lines.append(
                    f"- {repo.get('name')}: {repo.get('description') or ''} "
                    f"[{repo.get('language') or 'N/A'}] ⭐{repo.get('stargazers_count', 0)}"
                    + (f" | topics: {topics}" if topics else "")
                )
            if lines:
                repos_text = "\nRepositórios principais:\n" + "\n".join(lines)
    except Exception:
        pass

    text = (
        f"GitHub: {data.get('name', org)}\n"
        f"Descrição: {data.get('description') or 'N/A'}\n"
        f"Localização: {data.get('location') or 'N/A'}\n"
        f"Site: {data.get('blog') or 'N/A'}\n"
        f"Repositórios públicos: {data.get('public_repos', 0)}\n"
        f"Seguidores/membros: {data.get('followers', data.get('members_count', 0))}\n"
        + repos_text
    )
    return {
        "url": url, "text": text,
        "source": "github_api",
        "scraped_at": datetime.now().isoformat(),
    }


# ── Playwright fallback ───────────────────────────────────────────────────────

async def _scrape_playwright(url: str) -> dict | None:
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(extra_http_headers=_HEADERS)
            await page.goto(url, wait_until="domcontentloaded", timeout=22000)
            await page.wait_for_timeout(2500)
            html = await page.content()
            await browser.close()
        text = trafilatura.extract(html, include_links=False, no_fallback=False)
        if text and len(text) > 100:
            return {
                "url": url, "text": text[:8000],
                "source": "playwright",
                "scraped_at": datetime.now().isoformat(),
            }
    except Exception as e:
        print(f"[scraper:playwright] {url}: {e}")
    return None


# ── Plain HTTP ────────────────────────────────────────────────────────────────

async def _scrape_http(url: str, client: httpx.AsyncClient) -> dict | None:
    for attempt in range(2):
        try:
            r = await client.get(url, headers=_HEADERS, timeout=15, follow_redirects=True)
            r.raise_for_status()
            text = trafilatura.extract(r.text, include_links=False, no_fallback=False)
            if text and len(text) > 80:
                return {
                    "url": url, "text": text[:8000],
                    "source": "http",
                    "scraped_at": datetime.now().isoformat(),
                }
            return None
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (429, 503) and attempt == 0:
                await asyncio.sleep(2)
                continue
            return None
        except Exception as e:
            print(f"[scraper] {url}: {e}")
            return None
    return None


# ── Dispatcher ────────────────────────────────────────────────────────────────

async def scrape_url_async(url: str, client: httpx.AsyncClient) -> dict | None:
    domain = urlparse(url).hostname or ""

    if "github.com" in domain:
        result = await _scrape_github(url, client)
        if result:
            return result

    if any(d in domain for d in _JS_REQUIRED):
        return await _scrape_playwright(url)

    result = await _scrape_http(url, client)
    if result:
        return result

    return await _scrape_playwright(url)


# ── Public API ────────────────────────────────────────────────────────────────

async def scrape_startup_async(name: str, urls: list[str], save: bool = True) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        results = await asyncio.gather(*[scrape_url_async(url, client) for url in urls])

    pages = []
    seen: set[str] = set()
    for r in results:
        if r is None:
            continue
        sig = r["text"][:200]
        if sig in seen:
            continue
        seen.add(sig)
        pages.append(r)
        print(f"[scraper] ✓ {r['url']} [{r.get('source','?')}] ({len(r['text'])} chars)")

    output = {
        "startup": name,
        "scraped_at": datetime.now().isoformat(),
        "pages": pages,
    }

    if save:
        path = Path(f"data/raw/{name.lower().replace(' ', '_')}.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
        print(f"[scraper] salvo → {path} ({len(pages)} páginas)")

    return output


def scrape_startup(name: str, urls: list[str], save: bool = True) -> dict:
    return asyncio.run(scrape_startup_async(name, urls, save))


def scrape_url(url: str) -> dict | None:
    async def _run():
        async with httpx.AsyncClient() as client:
            return await _scrape_http(url, client)
    return asyncio.run(_run())


if __name__ == "__main__":
    import sys
    name = sys.argv[1] if len(sys.argv) > 1 else "Neoway"
    from agents.researcher import research_startup
    urls = research_startup(name)
    result = asyncio.run(scrape_startup_async(name, urls))
    print(f"\nPáginas coletadas: {len(result['pages'])}")
