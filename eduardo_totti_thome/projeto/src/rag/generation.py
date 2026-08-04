"""Geração com citação: o LLM responde usando os trechos recuperados, citando a fonte."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient

from rag.retrieval import search

load_dotenv()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

SYSTEM_PROMPT = (
    "Você responde perguntas sobre tecnologias NVIDIA usando APENAS os trechos "
    "fornecidos. Se a resposta não estiver nos trechos, diga que não há informação "
    "suficiente. Responda em português, de forma objetiva."
)


def _build_context(chunks: list[dict]) -> str:
    """Junta os trechos num texto único, cada um marcado com tecnologia e fonte."""
    return "\n\n".join(
        f"[Trecho {i} | {c['technology']} | {c['source_url']}]\n{c['text']}"
        for i, c in enumerate(chunks, 1)
    )

def answer_question(client: QdrantClient, query: str, limit: int = 3) -> dict:
    """Recupera trechos, pede ao LLM uma resposta baseada neles e devolve com as fontes.

    Retorna um dict: {'answer': str, 'sources': list[str]}.
    """
    chunks = search(client, query, limit=limit)
    if not chunks:
        return {"answer": "Não encontrei trechos relevantes na base.", "sources": []}

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Trechos:\n{_build_context(chunks)}\n\nPergunta: {query}"},
    ]

    llm = OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=os.getenv("OPENROUTER_API_KEY", "").strip(),
    )
    response = llm.chat.completions.create(
        model=os.getenv("OPENROUTER_MODEL", "").strip(),
        messages=messages,
        max_tokens=800,
    )

    if not response.choices:
        answer = "(o modelo não retornou resposta — instabilidade do tier grátis)"
    else:
        answer = response.choices[0].message.content or "(resposta vazia)"

    # fontes únicas, mantendo a ordem de relevância
    sources = list(dict.fromkeys(c["source_url"] for c in chunks))
    return {"answer": answer, "sources": sources}
