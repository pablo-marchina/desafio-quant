from __future__ import annotations

from functools import partial

from langgraph.graph import END, START, StateGraph

from src.storage import InMemoryStructuredRepository, StructuredRepository

from .nodes import (
    briefing_node,
    classifier_node,
    extractor_node,
    planner_node,
    rag_node,
    recommendation_node,
    route_after_validator,
    scraper_node,
    validator_node,
)
from .state import PipelineState


def build_startup_pipeline(
    repository: StructuredRepository | None = None,
):
    repository = repository or InMemoryStructuredRepository()
    graph = StateGraph(PipelineState)

    graph.add_node("planner", planner_node)
    graph.add_node("scraper", scraper_node)
    graph.add_node("extractor", extractor_node)
    graph.add_node("classifier", classifier_node)
    graph.add_node("validator", validator_node)
    graph.add_node("rag", rag_node)
    graph.add_node("recommendation", partial(recommendation_node, repository=repository))
    graph.add_node("briefing", briefing_node)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "scraper")
    graph.add_edge("scraper", "extractor")
    graph.add_edge("extractor", "classifier")
    graph.add_edge("classifier", "validator")
    graph.add_conditional_edges(
        "validator",
        route_after_validator,
        {
            "extractor": "extractor",
            "rag": "rag",
        },
    )
    graph.add_edge("rag", "recommendation")
    graph.add_edge("recommendation", "briefing")
    graph.add_edge("briefing", END)

    return graph.compile()
