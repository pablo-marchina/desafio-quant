"""LLM fact extraction node."""

from __future__ import annotations

from typing import Any

from .. import config
from ..state import EnrichmentState


def append_error(errors: object, source: str, message: str) -> object:
    if isinstance(errors, dict):
        merged = {key: list(value) if isinstance(value, list) else value for key, value in errors.items()}
        current = merged.get(source, [])
        if not isinstance(current, list):
            current = [str(current)]
        merged[source] = [*current, message]
        return merged
    return [*(errors or []), f"{source}: {message}"]


def build_llm(model: str | None = None) -> object:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model or config.OPENROUTER_MODEL,
        api_key=config.openrouter_api_key(),
        base_url=config.OPENROUTER_BASE_URL,
        default_headers={
            "HTTP-Referer": config.OPENROUTER_REFERER,
            "X-Title": config.OPENROUTER_TITLE,
        },
        temperature=0,
    )


def openrouter_models() -> list[str]:
    return list(dict.fromkeys([config.OPENROUTER_MODEL, *config.OPENROUTER_FALLBACK_MODELS]))


def invoke_llm(prompt: str) -> str:
    errors: list[str] = []
    for model in openrouter_models():
        try:
            response = build_llm(model).invoke(prompt)
            return str(getattr(response, "content", response)).strip()
        except Exception as error:
            errors.append(f"{model}: {error}")
    raise RuntimeError("Todos os modelos OpenRouter falharam: " + " | ".join(errors))


def summarize_evidence(evidence_summary: str) -> str:
    prompt = (
        "Escreva uma descricao verificavel em portugues, com no maximo 300 palavras, "
        "sobre o que a empresa faz e, quando houver evidencia, como ela usa IA. "
        "Inclua somente fatos apoiados nas evidencias. Se nao houver evidencia de IA, diga isso claramente. "
        "Tambem mencione, quando existir nas evidencias, ano de fundacao/inicio, mercado-alvo e setor. "
        "Nao invente informacoes ausentes.\n\n"
        f"EVIDENCIAS:\n{evidence_summary}"
    )
    return invoke_llm(prompt)[:2000]


def llm_summarize_node(state: EnrichmentState) -> dict[str, Any]:
    errors = state.get("errors", {})
    try:
        return {"llm_summary": summarize_evidence(state.get("evidence_summary", "")), "errors": errors}
    except Exception as error:
        return {"llm_summary": "", "errors": append_error(errors, "llm_summarize", str(error))}
