"""Scraper Agent: coloca o texto público da startup no estado.

Usa o coletor multi-página (home + páginas internas relevantes), do enriquecimento
da coleta — assim o Extractor e o Classifier recebem um texto mais rico.
"""

from __future__ import annotations

from graph.state import StartupState
from scraping.site_collector import collect_site_text

# Dois limiares de qualidade da coleta:
# - abaixo de MIN_CHARS_UTEIS: coleta FRACA -> ainda analisa, mas avisa.
# - abaixo de MIN_CHARS_MINIMO: coleta INSUFICIENTE -> nem dá pra classificar;
#   o grafo curto-circuita (ver route_after_scraper em graph/routing.py) e não
#   gasta as 4 chamadas de LLM. Bem mais baixo que o aviso de propósito: uma
#   coleta modesta (ex.: site institucional simples) ainda rende uma classificação
#   válida, então só abortamos quando voltou praticamente nada (típico de SPA/JS).
MIN_CHARS_UTEIS = 1000  # abaixo disso, a coleta é considerada fraca
MIN_CHARS_MINIMO = 200  # abaixo disso, é insuficiente para qualquer análise


def scraper_node(state: StartupState) -> dict:
    """Coleta o texto da startup (multi-página) e devolve no campo raw_text.

    Se a coleta vier fraca (pouco texto, típico de site SPA/JS), preenche um
    aviso em 'scrape_aviso' para o resultado deixar claro que a análise ficou
    limitada pela falta de conteúdo.
    """
    url = state["url"]
    # Na recoleta (ciclo do Evidence Validator, retries>0), busca MAIS páginas para
    # tentar trazer evidência adicional que resolva os "inconclusivo".
    max_pages = 10 if state.get("retries", 0) else 5
    texto = collect_site_text(url, max_pages=max_pages)

    aviso = ""
    if len(texto) < MIN_CHARS_UTEIS:
        aviso = (
            f"Coleta fraca: apenas {len(texto)} caracteres extraídos de {url}. "
            "O site pode ser renderizado por JavaScript (SPA); a análise pode estar limitada."
        )

    return {"raw_text": texto, "scrape_aviso": aviso}
