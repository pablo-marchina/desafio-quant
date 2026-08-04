"""Briefing Agent: gera o relatório executivo final para o gerente da NVIDIA."""

from __future__ import annotations

from agents.llm import ask_llm
from graph.state import StartupState

SYSTEM_PROMPT = (
    "Você redige um briefing executivo, em português e em markdown, para o gerente "
    "de Startups & VCs da NVIDIA Brasil (programa Inception). Tom construtivo e de "
    "apoio, linguagem objetiva. Estruture em seções: Resumo da startup; Classificação "
    "de maturidade (com a justificativa); Recomendações NVIDIA; Próxima ação sugerida. "
    "Escreva o markdown diretamente, sem envolver tudo em um bloco de código."
)


def briefing_node(state: StartupState) -> dict:
    """Sintetiza classificação + recomendações num relatório executivo."""
    checklist = state.get("checklist", [])
    checklist_txt = "\n".join(
        f"  {item.get('pergunta')}. {item.get('resposta')} - {item.get('evidencia')}"
        for item in checklist
    )

    recommendations = state.get("recommendations")
    if recommendations:
        rec_txt = f"Recomendações geradas:\n{recommendations}"
    else:
        # Caminho Non-AI: o grafo pulou o RAG e o recommender de propósito (nível 0).
        rec_txt = (
            "Sem recomendações NVIDIA por ora: a startup foi classificada como Non-AI "
            "(IA ausente ou apenas cosmética), então não há fit técnico no momento. "
            "Mantenha o tom de nutrir: aponte de forma construtiva o que mudaria esse "
            "quadro (ex.: adoção real de IA no produto) e sugira uma próxima ação leve "
            "de relacionamento, sem recomendar tecnologias NVIDIA específicas."
        )

    user_prompt = (
        f"Startup: {state.get('startup_name')}\n"
        f"Maturidade: nível {state.get('level')} ({state.get('level_name')})\n"
        f"Justificativa da classificação: {state.get('rationale')}\n\n"
        f"Checklist preenchido:\n{checklist_txt}\n\n"
        f"{rec_txt}\n\n"
        f"Escreva o briefing executivo."
    )

    briefing = ask_llm(SYSTEM_PROMPT, user_prompt, max_tokens=2000)
    return {"briefing": briefing}
