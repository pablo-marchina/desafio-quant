"""Search Planner Agent — primeira estação real do grafo (substitui o stub
`plan_node`). Recebe a `query` do gestor, chama um LLM com saída estruturada
e devolve termos de busca expandidos + fontes priorizadas dentre o catálogo
fixo (Grupo A — ver artefatos/backend.md §5).

Saída estruturada via `with_structured_output`: o LLM é forçado a devolver
algo que já bate com o schema `SearchPlan`, em vez de texto livre que
precisaria de parsing manual.
"""
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from agents.state import RadarState
from core.llm import get_llm
from scraping.registry import ADAPTERS

# O catálogo oferecido ao LLM é EXATAMENTE o conjunto de fontes que o sistema
# sabe raspar (scraping/registry.py). Não adianta o planner escolher uma fonte
# sem adapter — o scraper a ignoraria e a coleta viria vazia (era esse o bug:
# o LLM escolhia portais "famosos" como startse/endeavor que não temos como
# raspar). Amarrando ao registry, todo adapter novo entra aqui automaticamente
# e o planner só propõe o que é coletável.
#
# Catálogo futuro (Grupo A do artefatos/backend.md §5 — distrito, cubo, ace,
# endeavor, abstartups, liga.ventures, inovativabrasil, …) volta a este catálogo
# conforme cada adapter correspondente for implementado em scraping/.
SOURCE_CATALOG = sorted(ADAPTERS)

SYSTEM_PROMPT = """Você é o Search Planner do NVISION, um radar que mapeia \
startups brasileiras AI-native para o programa NVIDIA Inception.

Dada a consulta de um gestor, devolva:
1. `search_terms`: de 3 a 8 termos de busca em português, específicos \
(setor, tecnologia, estágio da startup), que ajudem a encontrar startups \
relevantes para a consulta.
2. `sources`: o subconjunto do catálogo abaixo mais relevante para essa \
consulta (pode ser todo o catálogo, se fizer sentido).
3. `reasoning`: uma frase explicando por que escolheu esses termos e fontes.

Catálogo de fontes permitido (escolha somente entre estas, exatamente como \
escritas):
{catalog}
"""


class SearchPlan(BaseModel):
    """Saída estruturada do LLM — schema que o `with_structured_output` força."""

    search_terms: list[str]
    sources: list[str]
    reasoning: str


def search_planner_node(state: RadarState) -> dict:
    """Nó 1 real do grafo: substitui o stub `plan_node`.

    Assinatura de 1 argumento (compatível com a convenção de nó do
    LangGraph). Chama `get_llm()` em tempo de execução (não no import), o
    que permite trocar essa referência por um LLM falso nos testes via
    `monkeypatch.setattr("agents.search_planner.get_llm", ...)`.
    """
    query = state.get("query", "")

    llm = get_llm()
    structured_llm = llm.with_structured_output(SearchPlan)

    prompt = [
        SystemMessage(content=SYSTEM_PROMPT.format(catalog="\n".join(SOURCE_CATALOG))),
        HumanMessage(content=query),
    ]
    plan: SearchPlan = structured_llm.invoke(prompt)

    # RECALL: o catálogo atual é só de diretórios GERAIS (não pesquisáveis por
    # setor), então restringir fontes não melhora o recall — varremos TODAS as
    # fontes com adapter. A seleção de fontes do LLM fica reservada para quando
    # houver fontes SETORIAIS (aí escolher faz diferença). O LLM segue valioso
    # pelos `search_terms`, que o filtro de relevância usa.
    sources = sorted(SOURCE_CATALOG)

    return {
        "search_terms": plan.search_terms,
        "sources": sources,
        "messages": [
            (
                "ai",
                f"[search_planner] {plan.reasoning} | termos: {plan.search_terms} | "
                f"fontes (todas): {sources}",
            )
        ],
    }
