import time
import re
import trafilatura
from bs4 import BeautifulSoup
import urllib.request
from duckduckgo_search import DDGS
from pipeline.config.settings import SCRAPING_DELAY_SECONDS, MAX_STARTUPS_PER_RUN

_DOMINIOS_BLOQUEADOS = [
    "facebook.com", "instagram.com", "youtube.com", "linkedin.com",
    "twitter.com", "x.com", "wikipedia.org", "crunchbase.com",
    "tiktok.com", "pinterest.com", "reddit.com",
    "g1.globo.com", "noticias.uol.com.br", "terra.com.br",
    "cnnbrasil.com.br", "r7.com", "band.com.br",
    "folha.uol.com.br", "estadao.com.br",
    "news.google.com",
    "yahoo.com", "bing.com",
    "adorocinema.com", "mmfilmes.com.br",
    "loterias.caixa.gov.br", "sbtpremios.com",
    "prodesp.sp.gov.br",
    "mercadolivre.com.br",
    "poder360.com.br", "metropoles.com",
    "diariodepernambuco.com.br", "folhape.com.br",
    "correiobraziliense.com.br",
]

_DOMINIOS_ECOSSISTEMA = [
    "startse.com", "distrito.me", "latitud.com", "cubo.network",
    "acestartups.com.br", "endeavor.org.br", "abstartups.com.br",
    "bossainvest.com", "anjosdobrasil.net", "darwinstartups.com",
    "liga.ventures", "wow.ac", "inovativabrasil.com.br",
    "openstartups.net", "startups.com.br", "braziljournal.com",
    "neofeed.com.br", "exame.com", "mobiletime.com.br",
    "pegn.globo.com", "valor.globo.com",
    "startupi.com.br",
]

_KEYWORDS_STARTUP = [
    "startup", "startups", "fundada", "fundado",
    "empreendedor", "empreendedorismo", "inovação", "inovador",
    "aceleradora", "investimento", "investidor",
    "rodada", "série a", "série b", "venture capital",
    "pj", "cnpj", "empresa", "solução", "plataforma",
    "aplicativo", "clientes", "crescimento",
    "tecnologia", "ia", "inteligência artificial", "machine learning",
    "site:", "ecossistema",
]


def _dominio_bloqueado(url: str) -> bool:
    for dom in _DOMINIOS_BLOQUEADOS:
        if dom in url:
            return True
    return False


def _dominio_ecossistema(url: str) -> bool:
    for dom in _DOMINIOS_ECOSSISTEMA:
        if dom in url:
            return True
    return False


def _conteudo_parece_startup(texto: str) -> bool:
    if not texto or len(texto) < 150:
        return False
    texto_lower = texto.lower()
    palavras_encontradas = sum(1 for kw in _KEYWORDS_STARTUP if kw in texto_lower)
    return palavras_encontradas >= 1


def _extrair_com_trafilatura(url: str) -> str | None:
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        return None
    return trafilatura.extract(downloaded, include_tables=True)


def _extrair_com_beautifulsoup(url: str) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        texto = soup.get_text(separator="\n")
        linhas = [l.strip() for l in texto.split("\n") if l.strip()]
        return "\n".join(linhas[:200])
    except Exception:
        return None


def _buscar_no_ddg(query: str, setor: str, max_resultados: int = 8) -> list[dict]:
    try:
        resultados = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_resultados):
                url = r.get("href", "")
                if not url:
                    continue
                if _dominio_bloqueado(url):
                    continue
                resultados.append({
                    "url": url,
                    "titulo": r.get("title", ""),
                    "fonte": "duckduckgo",
                    "setor": setor,
                    "tipo_fonte": "web"
                })
        return resultados
    except Exception:
        return []


def run_scraper(setor: str, queries: list[dict]) -> list[dict]:
    resultados_unicos = {}
    contador = 0

    for q in queries:
        if contador >= MAX_STARTUPS_PER_RUN:
            break

        query_texto = q.get("query", "")
        if not query_texto:
            continue

        print(f"[Scraper] Buscando: {query_texto}")
        found = _buscar_no_ddg(query_texto, setor)

        for item in found:
            url = item["url"]
            if url in resultados_unicos:
                continue

            if _dominio_bloqueado(url):
                continue

            print(f"[Scraper] Coletando: {url}")
            pagina = _extrair_com_trafilatura(url)
            if not pagina or len(pagina) < 150:
                pagina = _extrair_com_beautifulsoup(url)

            if pagina and len(pagina) >= 150:
                if _dominio_ecossistema(url) or _conteudo_parece_startup(pagina):
                    resultados_unicos[url] = {
                        "url": url,
                        "titulo": item.get("titulo", ""),
                        "conteudo_raw": pagina,
                        "fonte_origem": item.get("fonte", "duckduckgo"),
                        "setor": setor,
                        "tipo_fonte": "web"
                    }
                    contador += 1

            time.sleep(SCRAPING_DELAY_SECONDS)

        time.sleep(SCRAPING_DELAY_SECONDS)

    resultados = list(resultados_unicos.values())
    print(f"[Scraper] Total coletado: {len(resultados)} startups/páginas")
    return resultados
