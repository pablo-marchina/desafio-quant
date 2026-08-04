"""Cria a coleção de vetores no Qdrant (Bloco 2).

Roda uma vez para preparar o Qdrant. Seguro rodar de novo: se a coleção já
existe, não faz nada.

Uso:
    uv run python scripts/init_qdrant.py
"""

from __future__ import annotations

import sys

from rag.vector_store import COLLECTION_NAME, ensure_collection, get_client


def main() -> int:
    client = get_client()
    print(f"Conectando ao Qdrant e garantindo a colecao '{COLLECTION_NAME}'...")
    ensure_collection(client)

    # Confirma listando as coleções que existem agora no Qdrant.
    colecoes = [c.name for c in client.get_collections().collections]
    print(f"[OK] Colecoes no Qdrant: {colecoes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
