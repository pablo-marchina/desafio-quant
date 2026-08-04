"""Fallback de busca de notícias via GNews API (usado quando newsapi.org e newsdata.io falham)."""
from __future__ import annotations

import os

import requests

_BASE_URL = "https://gnews.io/api/v4/search"

_DOMINIOS_BLOQUEADOS = {
    "nature.com", "arxiv.org", "pubmed.ncbi.nlm.nih.gov", "sciencedirect.com",
    "springer.com", "wiley.com", "researchgate.net", "semanticscholar.org",
    "highsnobiety.com", "naturalnews.com",
}

_api_indisponivel = False


def _dominio_bloqueado(url: str) -> bool:
    from urllib.parse import urlparse
    host = urlparse(url).netloc.lower().lstrip("www.")
    return any(host == d or host.endswith("." + d) for d in _DOMINIOS_BLOQUEADOS)


def _item_valido(item: object) -> bool:
    """Valida schema mínimo de cada artigo retornado pelo GNews."""
    if not isinstance(item, dict):
        return False
    url = item.get("url")
    titulo = item.get("title")
    if not isinstance(url, str) or not url.startswith("http"):
        return False
    if not isinstance(titulo, str) or len(titulo.strip()) < 10:
        return False
    return True


def buscar(nome: str, debug: bool = False) -> list[dict]:
    """Busca artigos no GNews e normaliza para o mesmo formato do newsapi.org.

    Retorna lista de dicts com: title, description, url, publishedAt.
    Retorna lista vazia em caso de erro.
    """
    global _api_indisponivel
    if _api_indisponivel:
        return []

    api_key = os.environ.get("GNNEWS_API_KEY", "")
    if not api_key:
        print("      [fallback/gnews] GNNEWS_API_KEY não definida, pulando gnews")
        return []

    # Parênteses garantem que o nome seja obrigatório em todas as alternativas.
    q = (
        f'"{nome}" '
        f'("inteligência artificial" OR "machine learning" OR "IA generativa"'
        f' OR "chatbot" OR "automação inteligente" OR "LLM")'
    )
    params = {
        "token": api_key,
        "q": q,
        "lang": "pt",
        "country": "br",
        "max": 10,
        "sortby": "relevance",
    }

    if debug:
        print(f"      [fallback/gnews/debug] query: {q}")

    try:
        r = requests.get(_BASE_URL, params=params, timeout=10)

        if r.status_code in (401, 403, 429):
            print(f"      [fallback/gnews] API indisponível ({r.status_code}) — pulando para o restante da execução")
            _api_indisponivel = True
            return []
        if r.status_code >= 500:
            print(f"      [fallback/gnews] erro do servidor ({r.status_code})")
            return []

        r.raise_for_status()

    except requests.Timeout:
        print("      [fallback/gnews] timeout (10 s)")
        return []
    except requests.RequestException as e:
        print(f"      [fallback/gnews/erro] {e}")
        return []

    try:
        data = r.json()
    except ValueError:
        print("      [fallback/gnews/erro] resposta não é JSON válido")
        return []

    articles = data.get("articles")
    if not isinstance(articles, list):
        return []

    artigos = []
    for item in articles:
        if not _item_valido(item):
            continue
        url: str = item["url"]
        if _dominio_bloqueado(url):
            continue
        artigos.append({
            "title": item["title"],
            "description": item.get("description"),
            "url": url,
            "publishedAt": item.get("publishedAt"),
        })

    return artigos
