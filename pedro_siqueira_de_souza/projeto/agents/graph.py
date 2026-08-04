r"""Grafo LangGraph do NVISION.

Estações reais já implementadas:
  1. `search_planner_node` (LLM) — query -> termos de busca + fontes.
  2. `scraper_node`        — fontes -> startups cruas descobertas (pool amplo).
  2b. `relevance_node` (LLM) — filtra o pool pela CONSULTA, mantendo só as
                             startups relevantes ANTES do enriquecimento caro.
  3. `enricher_node`       — para quem tem detail_url, coleta o conteúdo da
                             página (trafilatura) -> matéria-prima do Extractor.
  4. `extractor_node` (LLM) — conteúdo bruto -> StructuredStartup (produto,
                             setor, estágio, funding, stack, sinais de IA).
  5. `classifier_node` (LLM) — StructuredStartup -> rótulo AI-native /
                             AI-enabled / Non-AI + justificativa e confiança.
  6. `evidence_validator_node` — valida a confiança por regras e, via ARESTA
                             CONDICIONAL, recoleta (volta pro scraper) quando a
                             evidência é fraca demais, ou segue pro RAG.
  7. `rag_node`            — consulta a base NVIDIA (Qdrant + Cohere Rerank) e
                             recupera, por startup, os trechos de tecnologia
                             mais relevantes ao perfil (insumo da recomendação).
  8. `recommendation_node` — converte o contexto RAG em recomendação de stack
                             NVIDIA por REGRAS (tech + confiança + citação).
  9. `briefing_node`       — consolida tudo num relatório executivo (markdown)
                             por startup, com citações e confiança.

Pipeline de coleta→qualificação→recomendação→relatório completo.

Fluxo atual (com ciclo condicional no evidence_validator):
    START -> search_planner -> scraper -> relevance -> enricher -> extractor
          -> classifier -> evidence_validator --(confiança baixa)--> scraper
            \--(ok)--> rag -> recommendation -> briefing -> END
"""
from langgraph.graph import END, START, StateGraph

from agents.briefing import briefing_node
from agents.classifier import classifier_node
from agents.enricher import enricher_node
from agents.evidence_validator import evidence_validator_node, route_after_validation
from agents.extractor import extractor_node
from agents.relevance import relevance_node
from agents.rag import rag_node
from agents.recommendation import recommendation_node
from agents.scraper import scraper_node
from agents.search_planner import search_planner_node
from agents.state import RadarState


def build_graph():
    """Monta e compila o grafo. Retorna um objeto invocável.

    StateGraph(RadarState): o estado que percorre o grafo.
    add_node:           registra uma função como nó.
    add_edge:           liga dois nós (aresta incondicional).
    add_conditional_edges: liga um nó a VÁRIOS destinos via uma função que
                        decide o caminho em runtime (o ciclo do validator).
    compile():          valida o grafo e devolve algo com `.invoke()`.
    """
    builder = StateGraph(RadarState)

    builder.add_node("search_planner", search_planner_node)
    builder.add_node("scraper", scraper_node)
    builder.add_node("relevance", relevance_node)
    builder.add_node("enricher", enricher_node)
    builder.add_node("extractor", extractor_node)
    builder.add_node("classifier", classifier_node)
    builder.add_node("evidence_validator", evidence_validator_node)
    builder.add_node("rag", rag_node)
    builder.add_node("recommendation", recommendation_node)
    builder.add_node("briefing", briefing_node)

    builder.add_edge(START, "search_planner")
    builder.add_edge("search_planner", "scraper")
    builder.add_edge("scraper", "relevance")
    builder.add_edge("relevance", "enricher")
    builder.add_edge("enricher", "extractor")
    builder.add_edge("extractor", "classifier")
    builder.add_edge("classifier", "evidence_validator")

    # Aresta CONDICIONAL: a função decide entre recoletar e seguir em frente.
    # `route_after_validation` devolve "scraper" (recoletar) ou END (seguir);
    # aqui o caminho de "seguir" é remapeado para o nó `rag` em vez de encerrar
    # — assim o validator não precisa conhecer a próxima estação. O grafo só
    # termina depois do RAG (aresta `rag -> END` abaixo).
    builder.add_conditional_edges(
        "evidence_validator",
        route_after_validation,
        {"scraper": "scraper", END: "rag"},
    )
    builder.add_edge("rag", "recommendation")
    builder.add_edge("recommendation", "briefing")
    builder.add_edge("briefing", END)

    return builder.compile()


# Grafo compilado pronto para importar (ex.: pela API).
graph = build_graph()


if __name__ == "__main__":
    # Execução manual — exige LLM_PROVIDER + chave no .env (search_planner usa
    # LLM) e acesso à rede (scraper renderiza um site real).
    resultado = graph.invoke({"query": "startups de IA generativa no Brasil"})
    print("Estado final:")
    for chave, valor in resultado.items():
        print(f"  {chave}: {valor}")
