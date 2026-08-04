"""Pipeline completa do Bloco 1: coleta e salva o conteúdo de uma startup.

Dado o nome de uma startup e a URL do site oficial, este script:
  1. baixa o HTML (Scrapling)
  2. extrai o texto limpo (trafilatura)
  3. salva no PostgreSQL com a fonte rastreável

É o "mínimo funcional" do Bloco 1 rodando de ponta a ponta.

Uso:
    uv run python scripts/collect_startup.py "Nome da Startup" https://www.site.com.br
"""

from __future__ import annotations

import sys

# Reunimos aqui as três peças que já construímos e validamos separadamente.
from db.repository import save_scraped_document
from scraping.scrapling_fetcher import fetch_html
from scraping.trafilatura_parser import extract_main_text

PREVIEW_CHARS = 500


def main() -> int:
    # Agora esperamos 3 itens em argv: o script, o NOME e a URL.
    # (O nome com espaços precisa vir entre aspas no terminal.)
    if len(sys.argv) != 3:
        print('Uso: uv run python scripts/collect_startup.py "Nome da Startup" <url>')
        return 1

    startup_name = sys.argv[1]
    url = sys.argv[2]

    print(f"Coletando '{startup_name}' a partir de {url}")

    # 1) BAIXAR — se falhar, paramos com mensagem amigável.
    try:
        html = fetch_html(url)
    except Exception as exc:  # noqa: BLE001 — queremos a mensagem, não o stack trace
        print(f"[FALHA] Nao consegui baixar a pagina: {exc}")
        return 1
    print(f"  HTML baixado: {len(html)} caracteres")

    # 2) LIMPAR — sem texto aproveitável, não há o que salvar.
    text = extract_main_text(html, url=url)
    if not text:
        print("[FALHA] O trafilatura nao encontrou texto principal — nada a salvar.")
        return 1
    print(f"  Texto limpo: {len(text)} caracteres")

    # 3) SALVAR — grava no banco e recebe o id da nova linha.
    doc_id = save_scraped_document(
        startup_name=startup_name,
        source_url=url,
        raw_text=text,
        source_type="site_oficial",
    )
    print(f"[OK] Salvo no banco com id = {doc_id}")

    # Preview do que foi salvo, só para conferência visual.
    print("\n----- preview do texto salvo -----")
    print(text[:PREVIEW_CHARS])
    if len(text) > PREVIEW_CHARS:
        print(f"\n... (+{len(text) - PREVIEW_CHARS} caracteres)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
