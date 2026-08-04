from __future__ import annotations

import functools
from typing import Any, Callable

from langgraph.graph import END, StateGraph

from radar.graph.edges import route_after_classification, route_after_validation
from radar.graph.nodes import (
    briefing_node,
    classifier_node,
    extractor_node,
    nvidia_rag_node,
    recommendation_node,
    scraper_node,
    search_planner_node,
    validator_node,
)
from radar.graph.progress import get_tracker
from radar.graph.state import RadarState

STEP_KEYS = {
    search_planner_node: "search_planner",
    scraper_node: "scraper",
    extractor_node: "extractor",
    classifier_node: "classifier",
    validator_node: "validator",
    nvidia_rag_node: "nvidia_rag",
    recommendation_node: "recommendation",
    briefing_node: "briefing",
}


def _with_progress(node_fn: Callable[[RadarState], dict[str, Any]]):
    step_key = STEP_KEYS[node_fn]

    @functools.wraps(node_fn)
    def wrapped(state: RadarState) -> dict[str, Any]:
        tracker = get_tracker()
        if tracker:
            tracker.start(step_key)
        try:
            result = node_fn(state)
            if tracker:
                tracker.complete(step_key)
            return result
        except Exception as exc:
            if tracker:
                tracker.fail(step_key, str(exc))
            raise

    return wrapped


def build_graph():
    graph = StateGraph(RadarState)

    graph.add_node("search_planner", _with_progress(search_planner_node))
    graph.add_node("scraper", _with_progress(scraper_node))
    graph.add_node("extractor", _with_progress(extractor_node))
    graph.add_node("validator", _with_progress(validator_node))
    graph.add_node("classifier", _with_progress(classifier_node))
    graph.add_node("nvidia_rag", _with_progress(nvidia_rag_node))
    graph.add_node("recommendation", _with_progress(recommendation_node))
    graph.add_node("briefing", _with_progress(briefing_node))

    graph.set_entry_point("search_planner")
    graph.add_edge("search_planner", "scraper")
    graph.add_edge("scraper", "extractor")
    graph.add_edge("extractor", "validator")
    graph.add_conditional_edges(
        "validator",
        route_after_validation,
        {
            "scraper": "scraper",
            "classifier": "classifier",
            "briefing": "briefing",
        },
    )
    graph.add_conditional_edges(
        "classifier",
        route_after_classification,
        {
            "nvidia_rag": "nvidia_rag",
            "briefing": "briefing",
        },
    )
    graph.add_edge("nvidia_rag", "recommendation")
    graph.add_edge("recommendation", "briefing")
    graph.add_edge("briefing", END)

    return graph.compile()
