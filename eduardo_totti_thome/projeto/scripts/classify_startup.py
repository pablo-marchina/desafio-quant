"""Classifica a maturidade de uma startup rodando o grafo completo (Bloco 3).

Uso:
    uv run python scripts/classify_startup.py "Nome da Startup" https://www.site.com.br
"""

from __future__ import annotations

import sys

from graph.pipeline import build_graph


def main() -> int:
    if len(sys.argv) != 3:
        print('Uso: uv run python scripts/classify_startup.py "Nome da Startup" <url>')
        return 1

    startup_name, url = sys.argv[1], sys.argv[2]

    graph = build_graph()
    print(f"Classificando '{startup_name}' ({url})...\n")
    final = graph.invoke({"startup_name": startup_name, "url": url})

    print(f"NIVEL: {final.get('level')} - {final.get('level_name')}")
    print(f"JUSTIFICATIVA: {final.get('rationale')}\n")
    print("CHECKLIST:")
    for item in final.get("checklist", []):
        print(f"  {item.get('pergunta')}. {item.get('resposta')} - {item.get('evidencia')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
