from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.briefing import build_briefing
from app.nvidia_context import build_research_with_nvidia_context
from app.recommendation import generate_recommendations
from app.rag.schemas import (
    BriefingResponse,
    RecommendationResponse,
    ResearchWithNvidiaContextResponse,
)
from app.research import run_research_pipeline
from app.schemas import ResearchRequest, ResearchResponse


class RadarState(TypedDict, total=False):
    payload: ResearchRequest
    research: ResearchResponse
    research_with_context: ResearchWithNvidiaContextResponse
    recommendations: RecommendationResponse
    briefing: BriefingResponse


async def research_agent(
    state: RadarState,
) -> dict[str, Any]:
    research = await run_research_pipeline(
        state["payload"]
    )

    return {
        "research": research,
    }


def nvidia_rag_agent(
    state: RadarState,
) -> dict[str, Any]:
    research_with_context = (
        build_research_with_nvidia_context(
            state["research"]
        )
    )

    return {
        "research_with_context": research_with_context,
    }


async def recommendation_agent(
    state: RadarState,
) -> dict[str, Any]:
    recommendations = await generate_recommendations(
        state["research_with_context"]
    )

    return {
        "recommendations": recommendations,
    }


def briefing_agent(
    state: RadarState,
) -> dict[str, Any]:
    briefing = build_briefing(
        research_with_context=state[
            "research_with_context"
        ],
        recommendation_response=state[
            "recommendations"
        ],
    )

    return {
        "briefing": briefing,
    }


def build_startup_radar_graph():
    workflow = StateGraph(RadarState)

    workflow.add_node(
        "research_agent",
        research_agent,
    )

    workflow.add_node(
        "nvidia_rag_agent",
        nvidia_rag_agent,
    )

    workflow.add_node(
        "recommendation_agent",
        recommendation_agent,
    )

    workflow.add_node(
        "briefing_agent",
        briefing_agent,
    )

    workflow.add_edge(
        START,
        "research_agent",
    )

    workflow.add_edge(
        "research_agent",
        "nvidia_rag_agent",
    )

    workflow.add_edge(
        "nvidia_rag_agent",
        "recommendation_agent",
    )

    workflow.add_edge(
        "recommendation_agent",
        "briefing_agent",
    )

    workflow.add_edge(
        "briefing_agent",
        END,
    )

    return workflow.compile()


startup_radar_graph = build_startup_radar_graph()