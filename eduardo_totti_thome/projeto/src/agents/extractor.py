"""Extractor Agent: transforma o texto bruto em dados estruturados (via LLM)."""

from __future__ import annotations

import json

from agents.llm import ask_llm
from graph.state import StartupState

SYSTEM_PROMPT = (
    "Você extrai informações de uma startup a partir do texto do site dela. "
    "Responda APENAS com um objeto JSON válido, sem texto fora dele, com as chaves: "
    "setor, produto, tecnologias_citadas (lista), sinais_time_tecnico (lista), "
    "usa_ia (string descrevendo se e como usa IA), evidencia_modelo_proprio (string), "
    'dados_proprietarios (string). Use "inconclusivo" quando o texto não disser.'
)


def _parse_json(text: str) -> dict:
    """Extrai o objeto JSON da resposta do LLM, tolerante a texto/fences em volta."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return {}
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}

def extractor_node(state: StartupState) -> dict:
    """Lê raw_text, pede ao LLM os dados estruturados e devolve em 'structured'."""
    raw_text = state.get("raw_text", "")
    if not raw_text:
        return {"structured": {}}

    # Limita o tamanho do texto enviado ao LLM (economia de tokens; o começo do
    # site costuma concentrar o essencial).
    user_prompt = f"Texto do site da startup:\n\n{raw_text[:4000]}"
    answer = ask_llm(SYSTEM_PROMPT, user_prompt)
    return {"structured": _parse_json(answer)}
