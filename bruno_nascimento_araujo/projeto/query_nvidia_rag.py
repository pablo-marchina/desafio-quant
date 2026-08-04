"""Fase 3 — NVIDIA RAG Agent (entrypoint CLI).

Uso:
  python query_nvidia_rag.py --startup-id 1 --dry-run
  python query_nvidia_rag.py --query "otimização de inferência de LLMs" --dry-run
  python query_nvidia_rag.py --startup-id 1 --top-k 5
  python query_nvidia_rag.py --startup-id 1 --categories "Inferência,Dados"
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import asyncpg
from qdrant_client import AsyncQdrantClient

from src.config import get_settings
from src.logging_conf import get_logger, setup_logging
from src.agents.rag_agent import RAGResult, run_rag

setup_logging()
logger = get_logger("rag.cli")

_SQL_MIGRATION = (Path(__file__).parent / "sql" / "004_rag_cache.sql").read_text()


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="NVIDIA RAG Agent: busca tecnologias NVIDIA relevantes para uma startup."
    )
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--startup-id", type=int, metavar="N",
                       help="ID da startup (usa transformação de query via LLM).")
    group.add_argument("--query", type=str, metavar="TEXTO",
                       help="Query textual direta para busca semântica.")
    p.add_argument("--top-k", type=int, default=5, metavar="N",
                   help="Número de chunks finais a retornar (padrão: 5).")
    p.add_argument("--categories", type=str, default=None, metavar="cat1,cat2",
                   help="Filtra por categorias separadas por vírgula (ex: Inferência,Dados).")
    p.add_argument("--dry-run", action="store_true",
                   help="Exibe resultado no console sem persistir no cache.")
    return p.parse_args()


def _print_result(result: RAGResult, dry_run: bool) -> None:
    prefix = "[DRY-RUN] " if dry_run else ""
    print(f"\n{'=' * 65}")
    print(f"{prefix}NVIDIA RAG — Resultados")
    print(f"{'=' * 65}")
    print(f"Query original   : {result.query}")
    print(f"Query de busca   : {result.condensed_query}")
    print(f"Retrieval        : {result.retrieval_time_ms:.0f} ms")
    if result.rerank_time_ms is not None:
        print(f"Reranking Cohere : {result.rerank_time_ms:.0f} ms")
    else:
        print("Reranking Cohere : N/A (fallback RRF)")
    print(f"{'─' * 65}")

    for i, chunk in enumerate(result.top_chunks, 1):
        print(f"\n[{i}] {chunk.tech_name}  ({chunk.category})  score={chunk.rerank_score:.4f}")
        print(f"    URL: {chunk.source_url}")
        print(f"    {chunk.text[:300].replace(chr(10), ' ')}")

    print(f"\n{'=' * 65}")

    # JSON completo para inspeção
    print("\nJSON completo (para integração):")
    print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2, default=str))


async def main() -> None:
    args = _parse_args()
    settings = get_settings()

    category_filter: list[str] | None = None
    if args.categories:
        category_filter = [c.strip() for c in args.categories.split(",") if c.strip()]

    pool: asyncpg.Pool = await asyncpg.create_pool(
        settings.database_url, min_size=2, max_size=5
    )
    await pool.execute(_SQL_MIGRATION)

    qdrant = AsyncQdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        check_compatibility=False,
    )

    try:
        result = await run_rag(
            startup_id=args.startup_id,
            query=args.query,
            top_k=args.top_k,
            category_filter=category_filter,
            pool=pool,
            qdrant=qdrant,
            dry_run=args.dry_run,
        )
        _print_result(result, dry_run=args.dry_run)
    finally:
        await pool.close()
        await qdrant.close()


if __name__ == "__main__":
    asyncio.run(main())
