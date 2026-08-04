"""Scraper Agent — segunda estação do grafo (substitui o antigo `echo_node`).

Lê `sources` (domínios escolhidos pelo Search Planner) do estado e, para cada
um que tenha adapter, descobre startups na listagem/portfólio. Escreve
`raw_startups` (ainda não estruturadas) para o Extractor Agent consumir.

Por que a orquestração mora aqui e a lógica de HTML não: o nó é AGNÓSTICO de
fonte. Toda a mecânica de cada site vive no adapter (scraping/). O nó apenas
itera, agrega e trata erro POR FONTE — uma fonte quebrada vira um log de erro,
não derruba a coleta inteira (tratamento de erro explícito).

Idempotente: re-executar (ex.: no loop de baixa confiança do Evidence
Validator) simplesmente recoleta e sobrescreve `raw_startups`.
"""
from loguru import logger

from agents.state import RadarState
from core.config import settings
from scraping.registry import get_adapter


def scraper_node(state: RadarState) -> dict:
    """Nó 2 real do grafo: descobre startups nas fontes selecionadas."""
    sources = state.get("sources", [])
    coletadas = []
    mensagens = []

    for dominio in sources:
        adapter = get_adapter(dominio)
        if adapter is None:
            # v1 ainda não cobre toda fonte do catálogo — segue em frente.
            mensagens.append(("ai", f"[scraper] {dominio}: sem adapter (ignorado)"))
            continue
        try:
            # POOL de descoberta por fonte: contribui nomes para o filtro de
            # relevância julgar (Relevance Agent). O teto do trabalho CARO
            # (enriquecimento) é aplicado lá, não aqui — aqui é só descoberta.
            achadas = adapter.discover()[: settings.max_startups_per_source]
            coletadas.extend(achadas)
            mensagens.append(("ai", f"[scraper] {dominio}: {len(achadas)} startups"))
        except Exception as e:  # uma fonte não pode derrubar as outras
            logger.exception("scraper falhou na fonte {}", dominio)
            mensagens.append(("ai", f"[scraper] {dominio} FALHOU: {e}"))

    return {
        "raw_startups": [s.model_dump() for s in coletadas],
        "messages": mensagens,
    }
