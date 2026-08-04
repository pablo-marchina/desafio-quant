"""Recommendation Agent: cruza o perfil da startup com as tecnologias NVIDIA recuperadas."""

from __future__ import annotations

from agents.llm import ask_llm
from graph.state import StartupState

SYSTEM_PROMPT = (
    "Você recomenda tecnologias NVIDIA para uma startup brasileira, de forma "
    "CONSTRUTIVA — o objetivo da NVIDIA é apoiar e atrair startups, não reprová-las. "
    "Baseie-se APENAS nas tecnologias presentes no contexto fornecido. Para cada "
    "tecnologia recomendada, dê uma justificativa técnica e uma de negócio, curtas. "
    "Se o contexto não trouxer nada aplicável, diga isso com honestidade. "
    "Responda em português."
)


def _format_context(chunks: list[dict]) -> str:
    """Junta os trechos NVIDIA recuperados num texto, marcando tecnologia e fonte."""
    return "\n\n".join(
        f"[{c.get('technology')} | {c.get('source_url')}]\n{c.get('text')}"
        for c in chunks
    )


def recommender_node(state: StartupState) -> dict:
    """Gera recomendações de tecnologias NVIDIA com base no perfil + contexto."""
    structured = state.get("structured", {})
    context = _format_context(state.get("nvidia_context", []))

    user_prompt = (
        f"Perfil da startup:\n"
        f"- Nome: {state.get('startup_name')}\n"
        f"- Maturidade: nível {state.get('level')} ({state.get('level_name')})\n"
        f"- Dados: {structured}\n\n"
        f"Tecnologias NVIDIA disponíveis (contexto recuperado):\n{context}\n\n"
        f"Recomende as tecnologias NVIDIA mais adequadas para esta startup, com justificativa."
    )

    recommendations = ask_llm(SYSTEM_PROMPT, user_prompt, max_tokens=1000)
    return {"recommendations": recommendations}
