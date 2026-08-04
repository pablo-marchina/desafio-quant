"""Registro fonte -> adapter.

O `scraper_node` recebe domínios (de `state['sources']`, escolhidos pelo
Search Planner dentre o SOURCE_CATALOG) e pergunta aqui qual adapter cuida de
cada um. Fontes sem adapter ainda são ignoradas com aviso — o v1 cobre só
parte do catálogo (começamos por portfólios de aceleradoras; ver ux.md §10).
"""
from scraping.anjos import AnjosAdapter
from scraping.base import SourceAdapter
from scraping.latitud import LatitudAdapter
from scraping.openstartups import OpenStartupsAdapter
from scraping.wow import WowAdapter

# domínio -> instância do adapter. Crescer aqui = nova fonte coberta.
ADAPTERS: dict[str, SourceAdapter] = {
    WowAdapter.domain: WowAdapter(),
    OpenStartupsAdapter.domain: OpenStartupsAdapter(),
    AnjosAdapter.domain: AnjosAdapter(),
    LatitudAdapter.domain: LatitudAdapter(),
}


def get_adapter(domain: str) -> SourceAdapter | None:
    """Adapter responsável por `domain`, ou None se ainda não houver um."""
    return ADAPTERS.get(domain)
