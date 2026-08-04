"""Pergunta à base NVIDIA via RAG: recupera trechos e gera resposta com citação.

Teste final do mínimo do Bloco 2.

Uso:
    uv run python scripts/ask_nvidia.py "sua pergunta aqui"
"""

from __future__ import annotations

import sys

from rag.generation import answer_question
from rag.vector_store import get_client


def main() -> int:
    if len(sys.argv) != 2:
        print('Uso: uv run python scripts/ask_nvidia.py "sua pergunta"')
        return 1

    query = sys.argv[1]
    client = get_client()
    result = answer_question(client, query)

    print(f"Pergunta: {query}\n")
    print("Resposta:")
    print(result["answer"])
    print("\nFontes:")
    for s in result["sources"]:
        print(f"  - {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
