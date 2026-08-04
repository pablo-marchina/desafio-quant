"""Search Planner Agent: descobre o site oficial da startup a partir do nome.

É o primeiro nó do grafo. Tira a necessidade de o usuário informar a URL: dado só
o nome, pergunta ao LLM qual é o site oficial. Se a URL já vier preenchida (uso
avançado / retrocompatibilidade), ele respeita e não sobrescreve.

Versão mínima de propósito: usa o próprio LLM (sem API de busca, que não está
configurada). Se não achar a URL, devolve vazio — o curto-circuito do grafo
(route_after_scraper) cuida do caso "site não encontrado".
"""

from __future__ import annotations

import re

from agents.llm import ask_llm
from graph.state import StartupState

SYSTEM_PROMPT = (
    "Você localiza o site oficial de startups e empresas brasileiras. Dado o nome, "
    "responda APENAS com a URL do site oficial, no formato https://dominio, sem mais "
    "nada. Se não tiver certeza de qual é o site oficial, responda exatamente: "
    "DESCONHECIDO."
)

# Pega a primeira URL http(s) numa resposta (tolerante a fences/aspas em volta).
_URL_RE = re.compile(r'https?://[^\s"\'<>)\]}`]+')


def _extract_url(text: str) -> str:
    """Extrai a primeira URL da resposta do LLM, limpando pontuação no final."""
    match = _URL_RE.search(text or "")
    if not match:
        return ""
    return match.group(0).rstrip(".,;)`")


def search_planner_node(state: StartupState) -> dict:
    """Descobre a URL a partir do nome. Se a URL já existe, mantém (não descobre)."""
    url = (state.get("url") or "").strip()
    if url:
        return {}  # URL fornecida — respeita e pula a descoberta

    nome = (state.get("startup_name") or "").strip()
    if not nome:
        return {"url": ""}

    answer = ask_llm(
        SYSTEM_PROMPT,
        f'Qual é o site oficial da startup brasileira "{nome}"?',
        max_tokens=100,
    )
    return {"url": _extract_url(answer)}
