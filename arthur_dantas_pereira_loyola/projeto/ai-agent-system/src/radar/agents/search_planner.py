from __future__ import annotations

from radar.schemas import SearchPlan

DEFAULT_SOURCE_TYPES = [
    "official_site",
    "blog",
    "careers",
    "startup_directory",
    "news",
]


def _expand_single_word(query: str, startup_name: str | None = None) -> list[str]:
    base = query.strip()
    expansions = [base]

    expansions.append(f"{base} IA")
    expansions.append(f"{base} inteligência artificial")
    expansions.append(f"{base} startup")
    expansions.append(f"{base} empresa tecnologia")
    expansions.append(f"{base} AI")
    expansions.append(f"{base} funding founders product")

    if startup_name and startup_name.strip().lower() != base.lower():
        sn = startup_name.strip()
        expansions.append(f"{sn} IA")

    return list(dict.fromkeys(expansions))


def _meaningful_terms(text: str) -> list[str]:
    stopwords = {
        "a", "as", "com", "de", "do", "da", "das", "dos",
        "e", "em", "ia", "o", "os", "para", "que", "um", "uma",
        "startup", "startups", "empresa", "empresas",
    }
    terms = []
    for raw in text.lower().replace("-", " ").replace("_", " ").split():
        t = "".join(c for c in raw if c.isalnum())
        if len(t) >= 3 and t not in stopwords:
            terms.append(t)
    return terms


def _generate_name_queries(
    startup_name: str, query: str
) -> list[str]:
    sn = startup_name.strip()
    if not sn:
        return []

    queries: list[str] = []
    queries.append(sn)
    queries.append(f"{sn} IA")
    queries.append(f"{sn} inteligência artificial")

    terms = _meaningful_terms(query)
    seen_terms: set[str] = set()
    for t in terms:
        if t.lower() not in sn.lower() and t not in seen_terms:
            queries.append(f"{sn} {t}")
            seen_terms.add(t)

    return list(dict.fromkeys(queries))


def plan_search(query: str, startup_name: str | None = None) -> SearchPlan:
    raw_keywords = [term.strip() for term in query.replace(",", " ").split() if term.strip()]
    is_short = len(raw_keywords) <= 1 and len(query.split()) <= 2

    name_queries = _generate_name_queries(startup_name, query) if startup_name else []

    if is_short:
        keywords = name_queries or _expand_single_word(query, startup_name)
        collection_plan = [
            f"Query curta '{query}' — expandindo busca para capturar contexto de startup/IA.",
            "Buscar site oficial, perfil de founders, funding e notícias.",
            "Preservar URLs e metadados de cada fonte.",
        ]
    else:
        keywords = raw_keywords or [query]
        if name_queries:
            keywords = name_queries + keywords
        collection_plan = [
            "Find official company pages and public startup directory entries.",
            "Collect news and blog pages that mention AI usage, product, customers, funding, or founders.",
            "Preserve URLs and retrieval metadata for every source.",
        ]

    return SearchPlan(
        query=query,
        keywords=keywords,
        source_types=DEFAULT_SOURCE_TYPES,
        collection_plan=collection_plan,
    )
