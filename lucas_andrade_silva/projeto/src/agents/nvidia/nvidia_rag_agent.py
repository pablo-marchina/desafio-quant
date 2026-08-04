from agents.nvidia.state import AgentState


def nvidia_rag_agent(state: AgentState) -> dict:
    from rag.generation.rag_query import generate_answer

    answer, results = generate_answer(
        state.get("rag_question") or state["question"],
        service=state.get("service"),
        category=state.get("category"),
    )
    sources = list(dict.fromkeys(result["source_url"] for result in results))
    update = {
        "rag_answer": answer,
        "retrieved_chunks": results,
        "sources": sources,
    }
    if state.get("output_mode", "briefing") == "rag":
        update["final_answer"] = answer
    return update
