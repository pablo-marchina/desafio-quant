"""Roda o radar completo para uma startup: scraping → classificação → recomendação → briefing.

É o MVP de ponta a ponta (Bloco 4).

Uso:
    uv run python scripts/run_radar.py "Nome da Startup" https://www.site.com.br
"""

from __future__ import annotations

import sys

from graph.pipeline import build_graph


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print('Uso: uv run python scripts/run_radar.py "Nome da Startup" [url-opcional]')
        return 1

    startup_name = sys.argv[1]
    url = sys.argv[2] if len(sys.argv) == 3 else ""

    graph = build_graph()
    if url:
        print(f"Rodando o radar para '{startup_name}' ({url})...\n")
    else:
        print(f"Rodando o radar para '{startup_name}' (descobrindo o site...)\n")
    final = graph.invoke({"startup_name": startup_name, "url": url})

    # Quando a URL não foi informada, mostra qual o Search Planner descobriu.
    site = final.get("url")
    if site and not url:
        print(f"Site descoberto: {site}\n")

    aviso = final.get("scrape_aviso")
    if aviso:
        print(f"[AVISO] {aviso}\n")

    nivel = final.get("level")
    if nivel is None:
        # Caminho de curto-circuito (coleta insuficiente): não houve classificação.
        print(f"Classificacao: {final.get('level_name')}\n")
    else:
        print(f"Classificacao: nivel {nivel} - {final.get('level_name')}\n")

    print("Tecnologias NVIDIA mais proximas do perfil (similaridade de cosseno, 0 a 1):")
    for c in final.get("nvidia_context", []):
        print(f"  {c.get('score'):.3f}  [{c.get('technology')}]  {c.get('source_url')}")
    print()

    print("=" * 60)
    print("BRIEFING EXECUTIVO")
    print("=" * 60)
    print(final.get("briefing") or "(briefing vazio - possivel instabilidade do LLM)")

    # Persiste a análise no Postgres. Opcional: se o banco não estiver no ar, apenas
    # avisa e segue — não derruba o resultado que já foi exibido acima.
    try:
        from db.repository import save_analysis
        from db.session import init_db

        init_db()  # cria a tabela 'analyses' se ainda não existir (idempotente)
        analysis_id = save_analysis(final)
        print(f"\n[persistido no Postgres: analise #{analysis_id}]")
    except Exception as e:  # noqa: BLE001 — persistência é opcional, não pode quebrar o run
        print(f"\n[aviso: analise nao persistida no Postgres: {type(e).__name__}: {e}]")

    return 0


if __name__ == "__main__":
    sys.exit(main())
