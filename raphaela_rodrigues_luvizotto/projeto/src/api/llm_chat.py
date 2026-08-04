from __future__ import annotations

import json
import os

import httpx
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from src.extraction.config import GROQ_API_KEY
from src.models import RagResult
from src.rag.api import answer_query
from src.rag.config import OPENROUTER_API_KEY, OPENROUTER_BASE, OPENROUTER_MODEL

GROQ_CHAT_MODEL = os.environ.get("CHAT_MODEL") or os.environ.get(
    "GROQ_MODEL", "llama-3.3-70b-versatile"
)
OPENROUTER_CHAT_MODEL = os.environ.get("CHAT_FALLBACK_MODEL") or os.environ.get(
    "OPENROUTER_CHAT_MODEL", OPENROUTER_MODEL
)


def _serialize_context(startup_payload: dict | None) -> str:
    if not startup_payload:
        return "Nenhuma startup previamente analisada foi selecionada."
    data = {
        "startup": startup_payload.get("name"),
        "segment": startup_payload.get("segment"),
        "city": startup_payload.get("city"),
        "aiScore": startup_payload.get("aiScore"),
        "classification": startup_payload.get("classification"),
        "validationStatus": startup_payload.get("validationStatus"),
        "summary": startup_payload.get("summary"),
        "signals": startup_payload.get("signals"),
        "recommendations": startup_payload.get("recommendations"),
        "briefing": startup_payload.get("executiveBrief"),
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def _build_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "Voce e um analista senior do NVIDIA Startup AI Radar. "
                    "Responda em portugues do Brasil, com tom executivo e objetivo. "
                    "Use o contexto da startup e o contexto RAG NVIDIA como base. "
                    "Se houver incerteza, explicite a limitacao em vez de inventar. "
                    "Se o contexto RAG estiver indisponivel, responda mesmo assim usando apenas "
                    "o contexto da startup e deixe claro que a resposta nao inclui recuperacao "
                    "da base NVIDIA nesta rodada."
                ),
            ),
            (
                "user",
                (
                    "Startup selecionada:\n{startup_context}\n\n"
                    "Status do RAG:\n{rag_status}\n\n"
                    "Contexto RAG NVIDIA:\n{rag_context}\n\n"
                    "Pergunta do usuario:\n{message}"
                ),
            ),
        ]
    )


def _build_prompt_messages(
    prompt: ChatPromptTemplate,
    message: str,
    startup_payload: dict | None,
    rag_context: RagResult,
    rag_warning: str | None,
):
    return prompt.format_messages(
        startup_context=_serialize_context(startup_payload),
        rag_status=rag_warning or "RAG disponivel",
        rag_context=json.dumps(rag_context.model_dump(), ensure_ascii=False, indent=2),
        message=message,
    )


def _invoke_groq(messages) -> tuple[str, str]:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY nao configurada para o chat.")

    llm = ChatGroq(
        model=GROQ_CHAT_MODEL,
        temperature=0.1,
        max_tokens=900,
        api_key=GROQ_API_KEY,
    )
    response = llm.invoke(messages)
    return response.content, "groq"


def _invoke_openrouter(messages) -> tuple[str, str]:
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY nao configurada para o fallback de chat.")

    payload = {
        "model": OPENROUTER_CHAT_MODEL,
        "messages": [
            {
                "role": "system" if index == 0 else "user",
                "content": message.content,
            }
            for index, message in enumerate(messages)
        ],
        "max_tokens": 900,
        "temperature": 0.1,
    }
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    response = httpx.post(
        f"{OPENROUTER_BASE}/v1/chat/completions",
        json=payload,
        headers=headers,
        timeout=30.0,
    )
    response.raise_for_status()
    data = response.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    if not content:
        raise RuntimeError("OpenRouter retornou resposta vazia para o chat.")
    return content, "openrouter"


def _build_local_fallback_answer(
    message: str,
    startup_payload: dict | None,
    rag_warning: str | None,
    provider_errors: list[str],
) -> str:
    startup_name = (startup_payload or {}).get("name") or "A startup selecionada"
    summary = (startup_payload or {}).get("summary") or "ainda nao tem resumo consolidado"
    classification = (startup_payload or {}).get("classification") or "Analise inicial"
    recommendations = (startup_payload or {}).get("recommendations") or []
    next_hint = recommendations[0]["nextStep"] if recommendations else "Reexecutar a analise quando o provedor de LLM voltar."

    limits = []
    if rag_warning:
        limits.append(f"RAG indisponivel: {rag_warning}")
    if provider_errors:
        limits.append(f"LLM indisponivel: {' | '.join(provider_errors)}")
    limits_text = " ".join(limits).strip()

    return (
        f"{startup_name}: {summary}. "
        f"Classificacao atual: {classification}. "
        f"Para a sua pergunta '{message}', consigo responder parcialmente com base no contexto ja analisado, "
        f"mas sem nova inferencia do modelo nesta rodada. "
        f"Proximo passo sugerido: {next_hint}. "
        f"{limits_text}"
    ).strip()


def answer_chat_message(message: str, startup_payload: dict | None = None) -> dict:
    rag_query = message
    if startup_payload and startup_payload.get("name"):
        rag_query = f"{startup_payload['name']} NVIDIA products fit {message}"

    rag_warning = None
    try:
        rag_context = answer_query(rag_query)
    except Exception as exc:
        rag_context = RagResult(query=rag_query, summary="", items=[], metadata={"status": "fallback"})
        rag_warning = str(exc)

    prompt = _build_prompt()
    messages = _build_prompt_messages(prompt, message, startup_payload, rag_context, rag_warning)

    provider_errors: list[str] = []
    provider_used = None
    answer = None

    try:
        answer, provider_used = _invoke_groq(messages)
    except Exception as exc:
        provider_errors.append(f"groq: {exc}")
        try:
            answer, provider_used = _invoke_openrouter(messages)
        except Exception as fallback_exc:
            provider_errors.append(f"openrouter: {fallback_exc}")
            answer = _build_local_fallback_answer(
                message,
                startup_payload,
                rag_warning,
                provider_errors,
            )
            provider_used = "local_fallback"

    return {
        "answer": answer,
        "provider": provider_used,
        "providerErrors": provider_errors,
        "ragStatus": "fallback" if rag_warning else "ok",
        "ragWarning": rag_warning,
        "sources": [
            {
                "citation": item.citation,
                "title": item.source_title,
                "url": item.source_url,
            }
            for item in rag_context.items[:5]
        ],
    }
