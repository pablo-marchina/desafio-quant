"""GitHub Agent (nó do grafo): junta sinais públicos do GitHub ao estado.

Nó fino: delega a coleta para scraping/github_scraper.py e guarda o resultado em
'github', para o Classifier usar como evidência de "produz vs. consome".
"""

from __future__ import annotations

from graph.state import StartupState
from scraping.github_scraper import fetch_github_signals


def github_node(state: StartupState) -> dict:
    """Busca a org no GitHub pelo nome da startup e guarda os sinais em 'github'."""
    signals = fetch_github_signals(state.get("startup_name", ""))
    return {"github": signals}
