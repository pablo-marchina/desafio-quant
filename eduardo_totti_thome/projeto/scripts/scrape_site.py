"""Demo do scraping de um site (Bloco 1 — sub-passo 1).

Recebe uma URL, baixa o HTML com o Scrapling, extrai o texto limpo com o
trafilatura e mostra um preview. Ainda não salva nada no banco — isso é o
próximo sub-passo.

Uso:
    uv run python scripts/scrape_site.py https://www.exemplo.com.br
"""

from __future__ import annotations

import sys

from scraping.scrapling_fetcher import fetch_html
from scraping.trafilatura_parser import extract_main_text

PREVIEW_CHARS = 1000


def main() -> int:
    if len(sys.argv) != 2:
        print("Uso: uv run python scripts/scrape_site.py <url>")
        return 1

    url = sys.argv[1]

    print(f"Baixando: {url}")
    try:
        html = fetch_html(url)
    except Exception as exc:  # noqa: BLE001 — demo: queremos a mensagem amigável
        print(f"[FALHA] {exc}")
        return 1

    print(f"HTML recebido: {len(html)} caracteres")

    text = extract_main_text(html, url=url)
    if not text:
        print("[AVISO] O trafilatura não encontrou texto principal nesta página.")
        return 1

    print(f"[OK] Texto limpo extraído: {len(text)} caracteres\n")
    print("----- preview -----")
    print(text[:PREVIEW_CHARS])
    if len(text) > PREVIEW_CHARS:
        print(f"\n... (+{len(text) - PREVIEW_CHARS} caracteres)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
