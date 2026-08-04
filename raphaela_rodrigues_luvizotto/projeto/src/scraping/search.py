"""
Search Planner simplificado (Dia 1).

No TAPI, o "Search Planner Agent" transforma a consulta do usuário em
termos de busca e fontes prioritárias. Por enquanto, fazemos a versão
mais simples possível: usamos a busca HTML do DuckDuckGo (não exige
API key, ótimo para começar sem bloqueio de credenciais) para achar
URLs candidatas a partir do nome da startup.

Evolução planejada: priorizar fontes da lista do TAPI (StartSe, Distrito,
Latitud, Cubo Itaú etc.) e usar um LLM (Groq) para gerar variações de
busca mais inteligentes.
"""
import logging
from urllib.parse import unquote, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

DUCKDUCKGO_HTML_URL = "https://html.duckduckgo.com/html/"


def _extrair_url_real(href: str) -> str:
    """
    O DuckDuckGo HTML às vezes retorna links de redirecionamento
    (//duckduckgo.com/l/?uddg=URL_REAL). Esta função extrai a URL real.
    """
    if "uddg=" in href:
        query = urlparse(href).query
        params = parse_qs(query)
        if "uddg" in params:
            return unquote(params["uddg"][0])
    return href


def buscar_urls_candidatas(nome_startup: str, max_resultados: int = 5) -> list[str]:
    """
    Busca URLs candidatas relacionadas a uma startup pelo nome.

    Retorna uma lista de URLs (pode vir vazia se a busca falhar ou
    não retornar nada — o pipeline deve lidar com isso graciosamente).
    """
    consulta = f"{nome_startup} startup brasil IA"

    try:
        resposta = requests.post(
            DUCKDUCKGO_HTML_URL,
            data={"q": consulta},
            headers=HEADERS,
            timeout=10,
        )

        if resposta.status_code == 403:
            logger.error(
                "DuckDuckGo bloqueou a requisição (403). Isso pode acontecer "
                "por rate-limit ou bloqueio anti-bot. Alternativas: tentar "
                "novamente em alguns segundos, ou usar fetch_page() "
                "diretamente com URLs conhecidas (ex: site da startup)."
            )
            return []

        resposta.raise_for_status()
    except requests.RequestException as exc:
        logger.error("Falha ao buscar URLs para '%s': %s", nome_startup, exc)
        return []

    soup = BeautifulSoup(resposta.text, "lxml")
    links = soup.find_all("a", class_="result__a")

    urls = []
    for link in links[:max_resultados]:
        href = link.get("href", "")
        url_real = _extrair_url_real(href)
        if url_real.startswith("http"):
            urls.append(url_real)

    if not urls:
        logger.warning("Nenhuma URL encontrada para a consulta: %s", consulta)

    return urls
