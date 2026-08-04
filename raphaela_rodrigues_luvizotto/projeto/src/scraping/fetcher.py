import logging

import requests
from bs4 import BeautifulSoup

from src.scraping.schema import ScrapedDocument

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; NVIDIAStartupRadarBot/0.1; "
        "+projeto academico Inteli)"
    )
}

TIMEOUT_SEGUNDOS = 10

# Tags que normalmente são ruído (navegação, scripts, etc.) e não
# fazem parte do conteúdo principal da página.
TAGS_PARA_REMOVER = ["script", "style", "nav", "footer", "header", "noscript"]


def fetch_page(url: str, fonte_tipo: str = "desconhecido") -> ScrapedDocument:
    """
    Busca uma URL e retorna um ScrapedDocument com o texto limpo.

    Sempre retorna um ScrapedDocument, mesmo em caso de erro
    (com o campo `erro` preenchido), para que o pipeline não quebre
    por causa de uma única URL com problema.
    """
    try:
        resposta = requests.get(url, headers=HEADERS, timeout=TIMEOUT_SEGUNDOS)
        status = resposta.status_code

        if status != 200:
            logger.warning("URL %s retornou status %s", url, status)
            return ScrapedDocument(
                url=url,
                titulo=None,
                texto="",
                fonte_tipo=fonte_tipo,
                status_http=status,
                erro=f"HTTP {status}",
            )

        soup = BeautifulSoup(resposta.text, "lxml")

        for tag in soup.find_all(TAGS_PARA_REMOVER):
            tag.decompose()

        titulo = soup.title.string.strip() if soup.title and soup.title.string else None

        texto_bruto = soup.get_text(separator="\n")
        linhas = [linha.strip() for linha in texto_bruto.splitlines()]
        texto_limpo = "\n".join(linha for linha in linhas if linha)

        return ScrapedDocument(
            url=url,
            titulo=titulo,
            texto=texto_limpo,
            fonte_tipo=fonte_tipo,
            status_http=status,
        )

    except requests.RequestException as exc:
        logger.error("Erro ao buscar %s: %s", url, exc)
        return ScrapedDocument(
            url=url,
            titulo=None,
            texto="",
            fonte_tipo=fonte_tipo,
            erro=str(exc),
        )
