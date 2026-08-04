"""Analisa em lote as startups do catálogo e salva no Postgres (popula o Radar de Mercado).

Pula as que já têm análise salva, então é seguro re-rodar. Uso:
    uv run python scripts/analyze_catalog.py         # analisa todas as pendentes
    uv run python scripts/analyze_catalog.py 5       # analisa só as 5 primeiras pendentes
"""

from __future__ import annotations

import sys

from db.catalog import get_catalog
from db.repository import save_analysis
from db.session import init_db
from graph.pipeline import build_graph


def main() -> int:
    init_db()
    limite = int(sys.argv[1]) if len(sys.argv) > 1 else 999
    pendentes = [c for c in get_catalog() if not c["analisada"]][:limite]

    if not pendentes:
        print("Nada pendente: todas as startups do catálogo já foram analisadas.")
        return 0

    grafo = build_graph()
    for i, c in enumerate(pendentes, 1):
        nome, url = c["startup_name"], c["url"]
        print(f"[{i}/{len(pendentes)}] Analisando {nome} ({url})...")
        try:
            final = grafo.invoke({"startup_name": nome, "url": url})
            save_analysis(final)
            print(f"   -> nivel {final.get('level')} ({final.get('level_name')}) salvo")
        except Exception as e:  # noqa: BLE001 — uma falha não pode abortar o lote
            print(f"   -> ERRO: {type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
