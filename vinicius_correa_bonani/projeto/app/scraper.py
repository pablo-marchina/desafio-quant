"""Scraper — coleta e extrai o texto público de cada URL.

Para cada URL do plano de busca: respeita robots.txt, baixa a página (httpx) e
extrai o texto principal (trafilatura). Guarda a fonte de cada trecho
(rastreabilidade). Funções separadas do nó para serem testáveis sem rede.
"""

from urllib.robotparser import RobotFileParser
from urllib.parse import urljoin, urlparse

import httpx
import trafilatura

from app.config import settings
from app.state import RadarState


def permitido_por_robots(url: str) -> bool:
    """Checa robots.txt do host. Em caso de falha ao ler, assume permitido."""
    try:
        base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        rp = RobotFileParser()
        rp.set_url(urljoin(base, "/robots.txt"))
        rp.read()
        return rp.can_fetch(settings.user_agent, url)
    except Exception:
        return True


def fetch_url(url: str) -> str | None:
    """Baixa o HTML da URL. Devolve None em erro/timeout."""
    try:
        resp = httpx.get(
            url,
            timeout=settings.http_timeout,
            follow_redirects=True,
            headers={"User-Agent": settings.user_agent},
        )
        resp.raise_for_status()
        return resp.text
    except Exception:
        return None


def extract_text(html: str) -> str:
    """Extrai o texto principal do HTML (sem menus/rodapé)."""
    texto = trafilatura.extract(html, include_comments=False, include_tables=False)
    return texto or ""


def scraper(state: RadarState) -> dict:
    # acumula entre as voltas do loop: parte do que já havia e só acrescenta fontes
    # novas (dedup por URL). Assim a busca dirigida ao gap SOMA evidência, não substitui.
    trechos: list[dict] = list(state.conteudo_bruto)
    ja_coletadas = {t.get("fonte") for t in trechos}
    for url in state.urls_busca:
        if url in ja_coletadas:
            continue
        if not permitido_por_robots(url):
            continue
        html = fetch_url(url)
        if not html:
            continue
        texto = extract_text(html)
        if texto.strip():
            trechos.append({"texto": texto, "fonte": url})
            ja_coletadas.add(url)
    return {"conteudo_bruto": trechos}
