# tests/test_search_planner.py
"""Testes do Search Planner Agent — sempre com LLM falso (patch_get_llm)."""
from agents.search_planner import SOURCE_CATALOG, search_planner_node


def test_search_planner_usa_termos_do_llm_e_todas_as_fontes(patch_get_llm, fixed_search_plan):
    resultado = search_planner_node({"query": "fintechs de IA"})

    assert resultado["search_terms"] == fixed_search_plan.search_terms
    # RECALL: varre TODAS as fontes com adapter, não só as que o LLM sugeriu.
    assert resultado["sources"] == sorted(SOURCE_CATALOG)
    assert len(resultado["messages"]) == 1


def test_search_planner_ignora_fontes_do_llm_e_varre_o_catalogo(patch_get_llm, fixed_search_plan):
    # Mesmo que o LLM sugira fontes parciais ou fora do catálogo, o planner
    # varre o catálogo inteiro (a escolha de fontes do LLM não gateia o recall).
    fixed_search_plan.sources = ["wow.ac", "site-fora-do-catalogo.com"]

    resultado = search_planner_node({"query": "qualquer coisa"})

    assert resultado["sources"] == sorted(SOURCE_CATALOG)
    assert "site-fora-do-catalogo.com" not in resultado["sources"]
