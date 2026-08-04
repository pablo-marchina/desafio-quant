"""Fallback de busca de notícias via newsdata.io (usado quando newsapi.org falha)."""
from __future__ import annotations

import os

import requests

_BASE_URL = "https://newsdata.io/api/1/news"

_DOMINIOS_BLOQUEADOS = {
    "nature.com", "arxiv.org", "pubmed.ncbi.nlm.nih.gov", "sciencedirect.com",
    "springer.com", "wiley.com", "researchgate.net", "semanticscholar.org",
    "highsnobiety.com", "naturalnews.com",
}

_cota_esgotada = False


def _dominio_bloqueado(url: str) -> bool:
    from urllib.parse import urlparse
    host = urlparse(url).netloc.lower().lstrip("www.")
    return any(host == d or host.endswith("." + d) for d in _DOMINIOS_BLOQUEADOS)


def _item_valido(item: object) -> bool:
    """Valida schema mínimo de cada resultado do newsdata.io."""
    if not isinstance(item, dict):
        return False
    url = item.get("link")
    titulo = item.get("title")
    if not isinstance(url, str) or not url.startswith("http"):
        return False
    if not isinstance(titulo, str) or len(titulo.strip()) < 10:
        return False
    return True


def buscar(nome: str, debug: bool = False) -> list[dict]:
    """Busca artigos no newsdata.io e normaliza para o mesmo formato do newsapi.org.

    Retorna lista de dicts com: title, description, url, publishedAt.
    Retorna lista vazia em caso de erro.
    """
    global _cota_esgotada
    if _cota_esgotada:
        return []

    api_key = os.environ.get("NEWS_DATA_KEY", "")
    if not api_key:
        print("      [fallback/newsdata] NEWS_DATA_KEY não definida, pulando newsdata.io")
        return []

    # Plano gratuito não suporta OR/parênteses — múltiplos termos são AND implícito.
    # Termos separados ampliam o match sem exigir a frase exata "inteligência artificial".
    q = f'"{nome}" inteligência artificial'
    params: dict = {
        "apikey": api_key,
        "q": q,
        "language": "pt",
        "country": "br",
    }

    if debug:
        print(f"      [fallback/newsdata/debug] query: {q}")

    try:
        r = requests.get(_BASE_URL, params=params, timeout=10)

        if r.status_code == 429:
            print("      [fallback/newsdata] cota diária esgotada — pulando para o restante da execução")
            _cota_esgotada = True
            return []
        if r.status_code >= 500:
            print(f"      [fallback/newsdata] erro do servidor ({r.status_code})")
            return []

        r.raise_for_status()

    except requests.Timeout:
        print("      [fallback/newsdata] timeout (10 s)")
        return []
    except requests.RequestException as e:
        print(f"      [fallback/newsdata/erro] {e}")
        return []

    try:
        data = r.json()
    except ValueError:
        print("      [fallback/newsdata/erro] resposta não é JSON válido")
        return []

    if data.get("status") != "success":
        print(f"      [fallback/newsdata/erro] status: {data.get('message') or data.get('results')}")
        return []

    results = data.get("results")
    if not isinstance(results, list):
        return []

    artigos = []
    for item in results:
        if not _item_valido(item):
            continue
        url: str = item["link"]
        if _dominio_bloqueado(url):
            continue
        artigos.append({
            "title": item["title"],
            "description": item.get("description"),
            "url": url,
            "publishedAt": item.get("pubDate"),  # normaliza para o campo padrão
        })

    return artigos
