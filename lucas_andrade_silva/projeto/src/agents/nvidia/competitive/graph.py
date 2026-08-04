from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agents.nvidia.briefing_agent import briefing_agent
from agents.nvidia.state import AgentState

from .agents import (
    bigtech_scraper_agent,
    bigtech_axis_summary_agent,
    comparison_agent,
    competitive_synthesis_agent,
    equivalence_validator_agent,
    leverage_agent,
    pricing_agent,
    search_string_generator_agent,
)


def route_after_scraper(state: AgentState) -> str:
    status = state.get("bigtech_validacao_status")
    if status == "esgotado":
        return "synthesis"
    if status == "rejeitado":
        return "scraper"
    return "validate"


def route_after_validation(state: AgentState) -> str:
    status = state.get("bigtech_validacao_status")
    if status == "confirmado":
        return "comparison"
    if status == "esgotado":
        return "synthesis"
    return "scraper"


def build_competitive_graph():
    builder = StateGraph(AgentState)
    builder.add_node("search_string", search_string_generator_agent)
    builder.add_node("scraper", bigtech_scraper_agent)
    builder.add_node("validate", equivalence_validator_agent)
    builder.add_node("comparison", comparison_agent)
    builder.add_node("axis_summary", bigtech_axis_summary_agent)
    builder.add_node("pricing", pricing_agent)
    builder.add_node("leverage", leverage_agent)
    builder.add_node("synthesis", competitive_synthesis_agent)
    builder.add_node("briefing", briefing_agent)

    builder.add_edge(START, "search_string")
    builder.add_edge("search_string", "scraper")
    builder.add_conditional_edges(
        "scraper",
        route_after_scraper,
        {
            "validate": "validate",
            "scraper": "scraper",
            "synthesis": "synthesis",
        },
    )
    builder.add_conditional_edges(
        "validate",
        route_after_validation,
        {
            "comparison": "comparison",
            "scraper": "scraper",
            "synthesis": "synthesis",
        },
    )
    builder.add_edge("comparison", "axis_summary")
    builder.add_edge("axis_summary", "pricing")
    builder.add_edge("pricing", "leverage")
    builder.add_edge("leverage", "synthesis")
    builder.add_edge("synthesis", "briefing")
    builder.add_edge("briefing", END)
    return builder.compile()
