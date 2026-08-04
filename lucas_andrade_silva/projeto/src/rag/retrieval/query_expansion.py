import os
import re

from groq import Groq

from rag.settings import required_env

PORTUGUESE_MARKERS = {
    "a",
    "as",
    "como",
    "com",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "entre",
    "é",
    "o",
    "os",
    "para",
    "por",
    "qual",
    "quais",
    "que",
    "serviço",
    "serviços",
    "uma",
}
STRONG_PORTUGUESE_MARKERS = {
    "como",
    "e",
    "entre",
    "é",
    "não",
    "para",
    "por",
    "qual",
    "quais",
    "que",
    "serviço",
    "serviços",
}


def is_likely_portuguese(query: str) -> bool:
    words = set(re.findall(r"\b[\wÀ-ÿ]+\b", query.casefold()))
    marker_count = len(words & PORTUGUESE_MARKERS)
    return (
        bool(words & STRONG_PORTUGUESE_MARKERS)
        or marker_count >= 2
        or bool(re.search(r"[ãõçáéíóúâêô]", query.casefold()))
    )


def parse_expansions(content: str, original_query: str, limit: int = 3) -> list[str]:
    original_normalized = original_query.casefold().strip()
    expansions = []

    for line in content.splitlines():
        cleaned = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip()
        cleaned = cleaned.strip("\"'")
        if (
            cleaned
            and cleaned.casefold() != original_normalized
            and cleaned.casefold() not in {item.casefold() for item in expansions}
        ):
            expansions.append(cleaned)
        if len(expansions) >= limit:
            break

    return expansions


def expand_query(query: str, expansion_count: int = 3) -> list[str]:
    if not is_likely_portuguese(query):
        return [query]

    prompt = f"""
Translate and expand the Portuguese search query below into {expansion_count}
distinct technical English queries for retrieving NVIDIA product and service
documentation.

Preserve every named NVIDIA product or service and the user's original intent.
Use terminology likely to appear in official NVIDIA documentation.
Do not introduce NVIDIA product, service, platform, framework, GPU, or model
names that are not explicitly present in the Portuguese query.
Return only one query per line, without numbering or explanations.

Portuguese query: {query}
""".strip()

    try:
        client = Groq(api_key=required_env("GROQ_API_KEY"))
        model = os.getenv(
            "GROQ_QUERY_EXPANSION_MODEL",
            "llama-3.3-70b-versatile",
        )
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a strict search-query translator. Never add "
                        "examples, explanations, or named entities that are "
                        "not present in the input query."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_completion_tokens=600,
        )
        content = response.choices[0].message.content or ""
        return [query, *parse_expansions(content, query, expansion_count)]
    except Exception as exc:
        print(f"  Expansao de query indisponivel; usando original: {exc}")
        return [query]
