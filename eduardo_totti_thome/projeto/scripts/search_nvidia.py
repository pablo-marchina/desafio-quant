"""Busca trechos relevantes na base NVIDIA do Qdrant (teste de recuperação).

Uso:
    uv run python scripts/search_nvidia.py "sua pergunta aqui"
"""

from __future__ import annotations

import sys

from rag.retrieval import search
from rag.vector_store import get_client


def main() -> int:
    if len(sys.argv) != 2:
        print('Uso: uv run python scripts/search_nvidia.py "sua pergunta"')
        return 1

    query = sys.argv[1]
    client = get_client()
    results = search(client, query)

    print(f"Pergunta: {query}\n")
    for i, r in enumerate(results, 1):
        print(f"#{i}  score={r['score']:.3f}  [{r['technology']}]")
        print(f"    fonte: {r['source_url']}")
        print(f"    trecho: {r['text'][:200]}...\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
