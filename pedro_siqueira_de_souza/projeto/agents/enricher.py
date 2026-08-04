"""Enricher Agent — terceira estação do grafo.

O Scraper *descobre* startups (nome + às vezes um link); o Enricher *coleta o
conteúdo* de cada uma. Para toda startup, garante um `detail_url` (descobrindo o
site oficial via BUSCA WEB quando a fonte só deu o nome), visita a página e
extrai o TEXTO PRINCIPAL com o trafilatura (remove menu/rodapé/anúncio — só o
conteúdo). É essa matéria-prima que o Extractor e o Classifier vão usar.

Decisões de design:
  - DESCOBERTA do site oficial: fontes como wow.ac/openstartups só dão o nome.
    Sem site, não há conteúdo para qualificar. `search_official_site` (DuckDuckGo)
    resolve o nome para a URL provável; o link descoberto é guardado em
    `detail_url` (vira proveniência depois).
  - STATIC-FIRST, DYNAMIC-FALLBACK: tenta `fetch_static` (HTTP puro, barato); se
    não vier texto aproveitável, ESCALA para `fetch_dynamic` (navegador real). A
    maioria dos sites de startup hoje é SPA (React/Next) que não renderiza nada
    sem JS — o HTTP puro voltava vazio, o trafilatura devolvia None e a startup
    caía em "metadata" (e era rotulada como Non-AI à toa). O navegador resolve
    isso, ao custo de ser mais lento — por isso só entra quando o estático falha.
  - Erro POR STARTUP: um site fora do ar / não encontrado vira `content=None`,
    não derruba os demais (mesma disciplina do Scraper).
  - Naturalmente educado com servidores: cada `detail_url` é um domínio
    diferente (o site da própria startup), então não martelamos ninguém.
"""
import trafilatura
from loguru import logger

from agents.state import RadarState
from scraping.fetch import ScrapeError, fetch_dynamic, fetch_static
from scraping.search import search_official_site


def _texto_estatico(url: str) -> str | None:
    """Tenta extrair o texto principal via HTTP puro (barato). None se falhar."""
    try:
        html = fetch_static(url).html_content
    except ScrapeError:
        return None
    # trafilatura devolve None quando não acha conteúdo principal aproveitável.
    return trafilatura.extract(html)


def _texto_dinamico(url: str) -> str | None:
    """Renderiza com navegador (para SPAs) e extrai o texto principal."""
    try:
        html = fetch_dynamic(url).html_content
    except ScrapeError:
        logger.warning("enricher: navegador falhou em {}", url)
        return None
    return trafilatura.extract(html)


def enricher_node(state: RadarState) -> dict:
    """Nó 3 do grafo: garante detail_url (via busca) e coleta o conteúdo."""
    raw_startups = state.get("raw_startups", [])

    enriquecidas = 0
    descobertos = 0
    via_navegador = 0
    atualizadas = []
    for rs in raw_startups:
        rs = dict(rs)  # cópia rasa — não muta o dict original do estado
        if not rs.get("content"):
            url = rs.get("detail_url")
            # Fonte só deu o nome? Descobre o site oficial via busca web.
            if not url:
                url = search_official_site(rs.get("name", ""), rs.get("sector"))
                if url:
                    rs["detail_url"] = url  # guarda o site descoberto
                    descobertos += 1
            if url:
                texto = _texto_estatico(url)
                # SPA? O estático veio vazio — escala para o navegador.
                if not texto:
                    texto = _texto_dinamico(url)
                    if texto:
                        via_navegador += 1
                if texto:
                    rs["content"] = texto
                    enriquecidas += 1
        atualizadas.append(rs)

    return {
        "raw_startups": atualizadas,
        "messages": [
            (
                "ai",
                f"[enricher] {enriquecidas}/{len(raw_startups)} enriquecidas "
                f"({descobertos} sites descobertos, {via_navegador} via navegador)",
            )
        ],
    }
