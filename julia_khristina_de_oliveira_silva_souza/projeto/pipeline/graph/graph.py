from langgraph.graph import StateGraph, END
from pipeline.graph.state import AgentState
from pipeline.graph.nodes import (
    node_search_planner,
    node_scraper,
    node_extractor,
    node_email_finder,
    node_classifier,
    node_evidence_validator,
    node_rag_agent,
    node_recommendation_agent,
    node_briefing_agent,
    should_continue_after_scraping,
    should_continue_after_validation,
)


def build_graph() -> StateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("search_planner", node_search_planner)
    workflow.add_node("scraper", node_scraper)
    workflow.add_node("extractor", node_extractor)
    workflow.add_node("email_finder", node_email_finder)
    workflow.add_node("classifier", node_classifier)
    workflow.add_node("evidence_validator", node_evidence_validator)
    workflow.add_node("rag_agent", node_rag_agent)
    workflow.add_node("recommendation_agent", node_recommendation_agent)
    workflow.add_node("briefing_agent", node_briefing_agent)

    workflow.set_entry_point("search_planner")

    workflow.add_edge("search_planner", "scraper")
    workflow.add_edge("scraper", "extractor")

    workflow.add_conditional_edges(
        "extractor",
        should_continue_after_scraping,
        {"continue": "email_finder", "stop": END}
    )
    workflow.add_edge("email_finder", "classifier")

    workflow.add_edge("classifier", "evidence_validator")

    workflow.add_conditional_edges(
        "evidence_validator",
        should_continue_after_validation,
        {"continue": "rag_agent", "stop": END}
    )

    workflow.add_edge("rag_agent", "recommendation_agent")
    workflow.add_edge("recommendation_agent", "briefing_agent")
    workflow.add_edge("briefing_agent", END)

    return workflow.compile()
