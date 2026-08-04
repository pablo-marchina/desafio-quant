"""Estado compartilhado do grafo de classificação (LangGraph).

É o "dicionário" que passa por todos os nós. Cada agente lê o que precisa e
acrescenta o seu resultado. Os campos vão sendo preenchidos ao longo do fluxo.
"""

from __future__ import annotations

from typing import TypedDict


class StartupState(TypedDict, total=False):
    # --- entrada (fornecida no início) ---
    startup_name: str
    url: str

    # --- preenchido pelo Scraper ---
    raw_text: str
    scrape_aviso: str  # aviso quando a coleta vem fraca (ex.: site SPA/JS)

    # --- preenchido pelo Extractor ---
    structured: dict

    # --- preenchido pelo GitHub Agent (sinal "produz vs. consome") ---
    github: dict

    # --- preenchido pelo Classifier ---
    checklist: list[dict]
    level: int
    level_name: str
    rationale: str

    # --- controle do ciclo do Evidence Validator ---
    retries: int       # quantas vezes já recoletamos (guard contra loop infinito)
    revalidar: bool    # o validator pediu nova coleta?

    # --- preenchido pelo NVIDIA RAG Agent ---
    nvidia_context: list[dict]

    # --- preenchido pelo Recommendation Agent ---
    recommendations: str

    # --- preenchido pelo Briefing Agent ---
    briefing: str
