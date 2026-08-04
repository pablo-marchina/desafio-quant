"""Vocabulário controlado de tecnologias — normalização de tags do filtro F5.11.

As facetas de tech da lista (F5.11) precisam ser **determinísticas e sem LLM**: a tech que a
startup usa (`Company.tecnologias`, sinais F1.11/F2.5) e a tech NVIDIA recomendada
(`Recommendation.tech`, F4.3) chegam com grafias soltas — "NVIDIA NIM", "NeMo Retriever (RAG)",
"lang chain" — que precisam colapsar numa **tag canônica** para o filtro ser exato (a UI só
oferece tags que existem; ver `apps/api/companies.py::list_tech_facets`).

A normalização é puro texto (offline, idempotente): limpa o nome (remove o qualificador entre
parênteses e o prefixo "NVIDIA"), colapsa espaços e resolve um pequeno mapa de **apelidos** para
a forma canônica. Apelidos só fundem variantes óbvias da mesma coisa ("triton inference server"
→ "Triton", "lang chain" → "LangChain"); famílias distintas (NeMo × NeMo Retriever × NeMo
Guardrails) seguem como tags **separadas** de propósito — são produtos diferentes. O que não está
no mapa volta limpo, preservando a grafia original (a faceta ainda funciona; só não funde).
"""

from __future__ import annotations

import re

#: Qualificador entre parênteses ("NeMo Retriever (RAG)" → "NeMo Retriever") — descritivo, não
#: faz parte da tag. Removido em qualquer posição.
_PAREN = re.compile(r"\s*\([^)]*\)")
#: Espaços repetidos colapsam em um (grafias coladas de fontes diferentes).
_WS = re.compile(r"\s+")
#: Prefixo de fornecedor — a tag canônica é o produto ("NVIDIA Riva" → "Riva").
_VENDOR_PREFIX = "nvidia "

#: Apelido (forma limpa, minúscula) → tag canônica. Funde só variantes da **mesma** tecnologia.
_ALIASES: dict[str, str] = {
    # família NVIDIA de inferência/dados
    "nim": "NIM",
    "triton": "Triton",
    "triton inference server": "Triton",
    "tensorrt-llm": "TensorRT-LLM",
    "tensorrt llm": "TensorRT-LLM",
    "trt-llm": "TensorRT-LLM",
    "rapids": "RAPIDS",
    "cudf": "cuDF",
    "cuml": "cuML",
    # ferramentas comuns do lado da startup
    "langchain": "LangChain",
    "lang chain": "LangChain",
    "llamaindex": "LlamaIndex",
    "llama index": "LlamaIndex",
    "openai": "OpenAI",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "huggingface": "Hugging Face",
    "hugging face": "Hugging Face",
    "sklearn": "scikit-learn",
    "scikit learn": "scikit-learn",
}


def _clean(name: str) -> str:
    """Remove parêntese descritivo, colapsa espaços e tira o prefixo/token de fornecedor."""
    s = _WS.sub(" ", _PAREN.sub("", name)).strip()
    low = s.lower()
    if low == _VENDOR_PREFIX.strip():  # "NVIDIA" sozinho não é uma tag
        return ""
    if low.startswith(_VENDOR_PREFIX):
        s = s[len(_VENDOR_PREFIX) :].strip()
    return s


def normalize_tech(name: str) -> str:
    """Canonicaliza um nome de tech para a tag do vocabulário controlado (F5.11).

    Idempotente: `normalize_tech(normalize_tech(x)) == normalize_tech(x)`. Devolve `""` para
    entrada vazia/só-prefixo (o caller descarta). Fora do mapa de apelidos, volta a forma limpa
    preservando a grafia (ex.: "Acme SDK" → "Acme SDK").
    """
    cleaned = _clean(name)
    if not cleaned:
        return ""
    return _ALIASES.get(cleaned.lower(), cleaned)


def normalize_techs(names: list) -> list[str]:
    """Normaliza uma lista de techs: descarta vazias e deduplica (case-insensitive), em ordem.

    Aceita strings ou dicts `{nome, ...}` (o formato JSON de `Company.tecnologias`, §2). Preserva
    a ordem da primeira ocorrência de cada tag.
    """
    out: list[str] = []
    seen: set[str] = set()
    for raw in names:
        nome = raw.get("nome") if isinstance(raw, dict) else raw
        if not nome:
            continue
        tag = normalize_tech(str(nome))
        key = tag.lower()
        if tag and key not in seen:
            seen.add(key)
            out.append(tag)
    return out


def tech_matches(needle: str | None, haystack: list[str]) -> bool:
    """Filtro determinístico: `needle` (normalizado) casa **exatamente** com uma tag da lista.

    `None`/vazio = sem filtro (passa tudo). `haystack` já vem normalizado (tags canônicas); a
    comparação é case-insensitive sobre a tag — sem substring, para o filtro ser do vocabulário
    controlado e não casar "NeMo" dentro de "NeMo Retriever".
    """
    if not needle:
        return True
    tag = normalize_tech(needle).lower()
    if not tag:
        return True
    return any(tag == name.lower() for name in haystack)


__all__ = ["normalize_tech", "normalize_techs", "tech_matches"]
