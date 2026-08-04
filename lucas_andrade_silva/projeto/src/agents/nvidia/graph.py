import argparse
import json
import sys
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from agents.nvidia.briefing_agent import briefing_agent
from agents.nvidia.competitive.graph import build_competitive_graph
from agents.nvidia.nvidia_rag_agent import nvidia_rag_agent
from agents.nvidia.gap_analysis_agent import gap_analysis_agent
from agents.nvidia.recommendation_agent import recommendation_agent
from agents.nvidia.state import AgentState, OutputMode
from agents.nvidia.startup_context_agent import (
    route_after_startup_context,
    startup_context_agent,
)
from rag.catalog import category_names, service_names

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def route_after_rag(state: AgentState) -> str:
    return "end" if state.get("output_mode", "briefing") == "rag" else "recommendation"


def route_after_recommendation(state: AgentState) -> str:
    if state.get("output_mode") == "competitive":
        return "competitive"
    return (
        "end"
        if state.get("output_mode", "briefing") == "recommendation"
        else "briefing"
    )


def build_graph():
    builder = StateGraph(AgentState)
    builder.add_node("startup_context", startup_context_agent)
    builder.add_node("nvidia_rag", nvidia_rag_agent)
    builder.add_node("gap_analysis", gap_analysis_agent)
    builder.add_node("recommendation", recommendation_agent)
    builder.add_node("briefing", briefing_agent)
    builder.add_node("competitive", build_competitive_graph())

    builder.add_edge(START, "startup_context")
    builder.add_conditional_edges(
        "startup_context",
        route_after_startup_context,
        {"rag": "nvidia_rag", "end": END},
    )
    builder.add_conditional_edges(
        "nvidia_rag",
        route_after_rag,
        {"recommendation": "gap_analysis", "end": END},
    )
    builder.add_edge("gap_analysis", "recommendation")
    builder.add_conditional_edges(
        "recommendation",
        route_after_recommendation,
        {"briefing": "briefing", "competitive": "competitive", "end": END},
    )
    builder.add_edge("briefing", END)
    builder.add_edge("competitive", END)
    return builder.compile()


graph = build_graph()


def infer_output_mode(question: str) -> OutputMode:
    normalized = " ".join(question.casefold().split())
    if "big tech" in normalized or "concorrente" in normalized:
        return "competitive"
    if (
        "match nvidia" in normalized
        or "recomende" in normalized
        or "recomendar" in normalized
        or "sugira" in normalized
        or "sugerir" in normalized
    ):
        return "recommendation"
    return "briefing"


def run_graph(
    question: str,
    output_mode: OutputMode = "briefing",
    service: str | None = None,
    category: str | None = None,
    competitive_context: dict | None = None,
) -> AgentState:
    initial_state = {
            "question": question,
            "output_mode": output_mode,
            "service": service,
            "category": category,
        }
    if competitive_context:
        initial_state.update(competitive_context)
    return graph.invoke(initial_state)


def run_competitive_analysis(
    delivery1_context: dict, question: str = "comparar com big techs"
) -> AgentState:
    """Executa só a Entrega 2 a partir do output estruturado da Entrega 1."""
    if not delivery1_context.get("servico_startup_analisado"):
        raise ValueError("servico_startup_analisado é obrigatório")
    initial = {
        **delivery1_context,
        "question": question,
        "output_mode": "competitive",
    }
    return build_competitive_graph().invoke(initial)


def main() -> None:
    parser = argparse.ArgumentParser(description="Executa os agentes NVIDIA.")
    parser.add_argument("question", nargs="+")
    parser.add_argument(
        "--mode",
        choices=("rag", "recommendation", "briefing", "competitive"),
        default=None,
    )
    parser.add_argument("--service", choices=service_names())
    parser.add_argument("--category", choices=category_names())
    parser.add_argument(
        "--context-file",
        help="JSON com o output da Entrega 1 (obrigatório para competitive).",
    )
    args = parser.parse_args()

    context = None
    if args.context_file:
        context = json.loads(Path(args.context_file).read_text(encoding="utf-8"))
    question = " ".join(args.question)
    selected_mode = args.mode or infer_output_mode(question)
    result = run_graph(
        question,
        output_mode=selected_mode,
        service=args.service,
        category=args.category,
        competitive_context=context,
    )
    print("\n" + "=" * 70)
    print(f"RESULTADO FINAL ({selected_mode.upper()})")
    print("=" * 70)
    print(result["final_answer"])
    if result.get("structured_output"):
        print("\nJSON ESTRUTURADO")
        print(
            json.dumps(
                result["structured_output"],
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
    print("\nFONTES")
    for source in result.get("sources", []):
        print(f"- {source}")


if __name__ == "__main__":
    main()
