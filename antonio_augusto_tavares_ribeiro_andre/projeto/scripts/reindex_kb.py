"""Re-indexa a KB NVIDIA no Qdrant com embeddings nv-embedqa reais (2048-dim).

Por que: a coleção `tapi_kb` foi semeada com o `HashingEmbedder` offline (256-dim, espinha
verde). Para ligar `INDEX_USE_QDRANT=true` e ter o **recommender RAG ao vivo com citação**
(F3.7) o índice precisa casar a dimensão do nv-embedqa (2048) — senão a busca dá
`Vector dimension error 256 != 2048`. Como `QdrantVectorIndex._ensure_collection` só cria a
coleção quando ela **não existe**, este script **dropa** a coleção atual e a reconstrói em
2048: embeda a KB inteira com `NVEmbedQA` (rede, ~créditos build.nvidia.com) e re-upserta.

Idempotente (reproduzível): roda o mesmo pipeline F3.1→F3.4 do `build_index`, só forçando o
embedder real + o índice Qdrant. Não toca a coorte (coleção/tabela separadas).

Uso (precisa `NVIDIA_API_KEY` no `.env` e o Qdrant no ar em `QDRANT_URL`):
    python scripts/reindex_kb.py            # dropa tapi_kb e reconstrói em 2048
    python scripts/reindex_kb.py --dry-run  # só reporta o estado atual, não escreve
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from packages.rag.embed import NV_EMBEDQA_DIM, NVEmbedQA, embed_kb  # noqa: E402
from packages.rag.index import QdrantVectorIndex, build_index  # noqa: E402


def _count(idx: QdrantVectorIndex) -> int:
    """Pontos na coleção (0 se ela não existe) — API robusta entre versões do client."""
    client = idx._ensure_client()
    if not client.collection_exists(idx.collection):
        return 0
    return client.count(idx.collection).count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Re-indexa tapi_kb em 2048 (nv-embedqa).")
    parser.add_argument("--dry-run", action="store_true", help="só reporta, não escreve.")
    args = parser.parse_args(argv)

    idx = QdrantVectorIndex()
    try:
        before = _count(idx)
    except Exception as exc:  # noqa: BLE001 — Qdrant indisponível: reporta e sai
        print(f"Qdrant indisponível em {idx.url}: {exc}", file=sys.stderr)
        return 1
    print(f"[antes]  coleção {idx.collection}: pontos={before}")
    if args.dry_run:
        return 0

    # 1) embeda a KB com o nv-embedqa real (2048-dim) — rede/créditos.
    embedder = NVEmbedQA()
    embedded = embed_kb(embedder=embedder)
    real_dim = embedded[0].dimension if embedded else 0
    print(f"[embed]  {len(embedded)} chunks com {embedder.model} → dim={real_dim}")
    if real_dim != NV_EMBEDQA_DIM:
        print(f"ERRO: dim {real_dim} != {NV_EMBEDQA_DIM} esperado do nv-embedqa", file=sys.stderr)
        return 1

    # 2) dropa a coleção antiga (256) p/ recriar na dimensão nova (o _ensure só cria se faltar).
    client = idx._ensure_client()
    if client.collection_exists(idx.collection):
        client.delete_collection(idx.collection)
        print(f"[drop]   coleção {idx.collection} removida")

    # 3) reconstrói (cria @2048 no 1º upsert) e re-upserta os pontos híbridos (denso + BM25).
    build_index(embedded=embedded, index=idx)

    after = _count(idx)
    print(f"[depois] coleção {idx.collection}: pontos={after}")
    if after != len(embedded):
        print(f"ERRO: {after} pontos != {len(embedded)} embedados", file=sys.stderr)
        return 1
    print(f"OK — KB re-indexada em nv-embedqa ({real_dim}-dim). Ligue INDEX_USE_QDRANT=true.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
