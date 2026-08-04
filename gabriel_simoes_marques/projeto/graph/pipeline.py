from langgraph.graph import StateGraph, END

from graph.state import PipelineState
from scraping.generic import scrape_startup_async
from agents.extractor import extract_startup_async
from agents.recommendation import generate_recommendations
from agents.briefing import generate_briefing
from rag.graphiti_client import get_graphiti
from config.llm import DEFAULT_MODEL


async def node_scrape(state: PipelineState) -> PipelineState:
    urls = state["urls"]
    if not urls:
        from agents.researcher import _research_async
        urls = await _research_async(state["startup_name"])
    await scrape_startup_async(state["startup_name"], urls, save=True)
    return {**state, "urls": urls}


async def node_extract(state: PipelineState) -> PipelineState:
    path = f"data/raw/{state['startup_name'].lower().replace(' ', '_')}.json"
    model = state.get("model", DEFAULT_MODEL)
    startup = await extract_startup_async(path, model=model)
    if startup is None:
        return {**state, "error": "Falha na extração da startup"}
    return {**state, "startup": startup}


async def node_recommend(state: PipelineState) -> PipelineState:
    model = state.get("model", DEFAULT_MODEL)
    graphiti = await get_graphiti()
    recommendations = await generate_recommendations(state["startup"], graphiti, model=model)
    await graphiti.close()
    return {**state, "recommendations": recommendations}


async def node_brief(state: PipelineState) -> PipelineState:
    model = state.get("model", DEFAULT_MODEL)
    briefing = await generate_briefing(state["startup"], state["recommendations"], model=model)
    return {**state, "briefing": briefing}


def should_continue(state: PipelineState) -> str:
    if state.get("error"):
        return END
    if state.get("startup") is None:
        return END
    return "recommend"


def build_pipeline():
    graph = StateGraph(PipelineState)

    graph.add_node("scrape", node_scrape)
    graph.add_node("extract", node_extract)
    graph.add_node("recommend", node_recommend)
    graph.add_node("brief", node_brief)

    graph.set_entry_point("scrape")
    graph.add_edge("scrape", "extract")
    graph.add_conditional_edges("extract", should_continue, {"recommend": "recommend", END: END})
    graph.add_edge("recommend", "brief")
    graph.add_edge("brief", END)

    return graph.compile()


pipeline = build_pipeline()
