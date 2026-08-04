import argparse
import json
import sys

import cohere
import torch
from FlagEmbedding import BGEM3FlagModel
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue
from rank_bm25 import BM25Okapi

from rag.catalog import category_names, detect_services, service_names
from rag.retrieval.utils import (
    fuse_ranked_groups,
    matches_scope,
    select_adaptive_results,
    tokenize,
    weighted_rrf,
)
from rag.retrieval.query_expansion import expand_query
from rag.settings import (
    CHUNKS_PATH,
    EMBEDDING_MODEL,
    QDRANT_COLLECTION,
    QDRANT_HOST,
    QDRANT_PORT,
    QDRANT_TIMEOUT,
    required_env,
)

RRF_K = 60
VECTOR_WEIGHT = 0.6
BM25_WEIGHT = 0.4

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_chunks: list[dict] | None = None
_bm25: BM25Okapi | None = None
_client_qdrant: QdrantClient | None = None
_client_cohere: cohere.Client | None = None
_model: BGEM3FlagModel | None = None


def _load_runtime() -> tuple[list[dict], BM25Okapi, QdrantClient, cohere.Client, BGEM3FlagModel]:
    global _chunks, _bm25, _client_qdrant, _client_cohere, _model

    if _chunks is None:
        with CHUNKS_PATH.open("r", encoding="utf-8") as file:
            _chunks = json.load(file)

    if _bm25 is None:
        _bm25 = BM25Okapi([tokenize(chunk["text"]) for chunk in _chunks])
        print(f"BM25 indexado com {len(_chunks)} chunks.")

    if _client_qdrant is None:
        _client_qdrant = QdrantClient(
            host=QDRANT_HOST,
            port=QDRANT_PORT,
            timeout=QDRANT_TIMEOUT,
        )

    collection_info = _client_qdrant.get_collection(QDRANT_COLLECTION)
    if collection_info.points_count != len(_chunks):
        raise RuntimeError(
            f"Qdrant possui {collection_info.points_count} pontos, mas "
            f"{CHUNKS_PATH.name} possui {len(_chunks)} chunks. "
            "Execute rag.ingestion.embed_and_store novamente."
        )

    if _client_cohere is None:
        _client_cohere = cohere.Client(api_key=required_env("COHERE_API_KEY"))

    if _model is None:
        use_fp16 = torch.cuda.is_available()
        print(f"Carregando {EMBEDDING_MODEL} (FP16={use_fp16})...")
        _model = BGEM3FlagModel(EMBEDDING_MODEL, use_fp16=use_fp16)
        print("Modelo carregado!")

    return _chunks, _bm25, _client_qdrant, _client_cohere, _model


def build_qdrant_filter(service: str | None, category: str | None) -> Filter | None:
    conditions = []
    if service:
        conditions.append(FieldCondition(key="services", match=MatchValue(value=service)))
    if category:
        conditions.append(FieldCondition(key="categories", match=MatchValue(value=category)))
    return Filter(must=conditions) if conditions else None


def search(
    query: str,
    service: str | None = None,
    category: str | None = None,
    top_k: int = 20,
    top_fusion: int = 20,
    top_rerank: int = 5,
    max_per_source: int = 2,
    min_relevance_score: float | None = 0.2,
) -> list[dict]:
    chunks, bm25, client_qdrant, client_cohere, model = _load_runtime()
    print(f"\nQuery: '{query}' | service={service} | category={category}")
    target_services = [service] if service else detect_services(query)
    if target_services:
        print(f"  Servicos detectados: {', '.join(target_services)}")

    query_variants = expand_query(query)
    if len(query_variants) > 1:
        print(f"  Expansoes em ingles: {len(query_variants) - 1}")
        for expansion in query_variants[1:]:
            print(f"    - {expansion}")

    query_vectors = model.encode(
        query_variants,
        return_dense=True,
        return_sparse=False,
        return_colbert_vecs=False,
    )["dense_vecs"]
    bm25_score_sets = [
        bm25.get_scores(tokenize(query_variant))
        for query_variant in query_variants
    ]

    def retrieve_scope(
        query_index: int,
        scope_service: str | None,
        scope_category: str | None,
        limit: int,
    ) -> list[dict]:
        vector_results = client_qdrant.query_points(
            collection_name=QDRANT_COLLECTION,
            query=query_vectors[query_index].tolist(),
            query_filter=build_qdrant_filter(scope_service, scope_category),
            limit=limit,
        ).points
        vector_hits = {
            hit.payload["chunk_id"]: {
                **hit.payload,
                "vector_score": hit.score,
            }
            for hit in vector_results
        }

        scoped_indices = [
            index
            for index, chunk in enumerate(chunks)
            if matches_scope(chunk, scope_service, scope_category)
        ]
        top_bm25_indices = sorted(
            scoped_indices,
            key=lambda index: bm25_score_sets[query_index][index],
            reverse=True,
        )[:limit]
        bm25_hits = {
            chunks[index]["chunk_id"]: {
                **chunks[index],
                "bm25_score": bm25_score_sets[query_index][index],
            }
            for index in top_bm25_indices
        }
        return weighted_rrf(
            vector_hits,
            bm25_hits,
            vector_weight=VECTOR_WEIGHT,
            bm25_weight=BM25_WEIGHT,
            rrf_k=RRF_K,
        )

    adaptive_top_k = max(top_k, 20 + 5 * len(target_services))
    adaptive_fusion = max(top_fusion, 20 + 5 * len(target_services))
    candidate_groups = []
    group_weights = []
    dedicated_retrievals = 0

    for query_index in range(len(query_variants)):
        variant_weight = 1.0 if query_index == 0 else 0.8
        fused = retrieve_scope(query_index, service, category, adaptive_top_k)
        candidate_groups.append(fused[:adaptive_fusion])
        group_weights.append(variant_weight)

        if not service:
            for target_service in target_services:
                scoped = retrieve_scope(query_index, target_service, category, top_k)
                candidate_groups.append(scoped[:12])
                group_weights.append(variant_weight)
                dedicated_retrievals += 1

    adaptive_rerank_pool = max(
        60,
        30 + 10 * len(query_variants) + 5 * len(target_services),
    )
    combined = fuse_ranked_groups(
        candidate_groups,
        group_weights,
        RRF_K,
    )[:adaptive_rerank_pool]
    print(
        f"  Bi-encoder + BM25 + RRF multi-query: {len(combined)} candidatos "
        f"({dedicated_retrievals} recuperacoes dedicadas)"
    )

    if not combined:
        return []

    rerank_response = client_cohere.rerank(
        model="rerank-v3.5",
        query=query,
        documents=[chunk["text"] for chunk in combined],
        top_n=len(combined),
    )
    reranked = [
        {
            **combined[hit.index],
            "relevance_score": hit.relevance_score,
        }
        for hit in rerank_response.results
    ]
    filtered_reranked = reranked
    if min_relevance_score is not None:
        filtered_reranked = [
            result
            for result in reranked
            if result["relevance_score"] >= min_relevance_score
        ]

    for target_service in target_services:
        selected_sources = {
            result["source_url"]
            for result in filtered_reranked
            if target_service in result["services"]
        }
        for fallback in reranked:
            if len(selected_sources) >= 2:
                break
            if (
                target_service in fallback["services"]
                and fallback["source_url"] not in selected_sources
                and fallback not in filtered_reranked
            ):
                filtered_reranked.append(fallback)
                selected_sources.add(fallback["source_url"])
    filtered_reranked.sort(key=lambda result: result["relevance_score"], reverse=True)

    diverse_results = select_adaptive_results(
        filtered_reranked,
        target_services,
        min_results=top_rerank,
        max_per_source=max_per_source,
    )
    print(
        f"  Cross-encoder + cobertura + diversidade: {len(diverse_results)} chunks, "
        f"{len({result['source_url'] for result in diverse_results})} fontes"
    )
    return diverse_results


def display_results(results: list[dict]) -> None:
    print("\n" + "=" * 60)
    print("RESULTADOS FINAIS")
    print("=" * 60)
    for index, result in enumerate(results, start=1):
        print(
            f"\nResultado {index} | Cohere: {result['relevance_score']:.4f} "
            f"| RRF: {result['rrf_score']:.6f}"
        )
        print(f"Servicos: {', '.join(result['services'])}")
        print(f"Categorias: {', '.join(result['categories'])}")
        print(f"Fonte: {result['source_url']}")
        print(f"Texto:\n{result['text'][:400]}...")


def main() -> None:
    parser = argparse.ArgumentParser(description="Busca hibrida no catalogo NVIDIA.")
    parser.add_argument("query", nargs="+")
    parser.add_argument("--service", choices=service_names())
    parser.add_argument("--category", choices=category_names())
    args = parser.parse_args()

    display_results(search(" ".join(args.query), args.service, args.category))


if __name__ == "__main__":
    main()
