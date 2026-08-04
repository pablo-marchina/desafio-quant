import re
from collections import defaultdict


def tokenize(text: str) -> list[str]:
    return re.findall(r"\b[\w.-]+\b", text.lower())


def weighted_rrf(
    vector_hits: dict,
    bm25_hits: dict,
    vector_weight: float,
    bm25_weight: float,
    rrf_k: int,
) -> list:
    fused = {}

    for rank, (chunk_id, hit) in enumerate(vector_hits.items(), start=1):
        fused[chunk_id] = hit.copy()
        fused[chunk_id]["vector_rank"] = rank
        fused[chunk_id]["rrf_score"] = vector_weight / (rrf_k + rank)

    for rank, (chunk_id, hit) in enumerate(bm25_hits.items(), start=1):
        if chunk_id not in fused:
            fused[chunk_id] = hit.copy()
            fused[chunk_id]["rrf_score"] = 0.0

        fused[chunk_id]["bm25_rank"] = rank
        fused[chunk_id]["bm25_score"] = hit["bm25_score"]
        fused[chunk_id]["rrf_score"] += bm25_weight / (rrf_k + rank)

    return sorted(fused.values(), key=lambda hit: hit["rrf_score"], reverse=True)


def fuse_ranked_groups(
    ranked_groups: list[list[dict]],
    group_weights: list[float],
    rrf_k: int,
) -> list[dict]:
    fused = {}

    for group, weight in zip(ranked_groups, group_weights, strict=True):
        for rank, hit in enumerate(group, start=1):
            chunk_id = hit["chunk_id"]
            if chunk_id not in fused:
                fused[chunk_id] = hit.copy()
                fused[chunk_id]["rrf_score"] = 0.0
            fused[chunk_id]["rrf_score"] += weight / (rrf_k + rank)

    return sorted(fused.values(), key=lambda hit: hit["rrf_score"], reverse=True)


def filter_diversity(results: list, max_per_source: int = 2) -> list:
    seen = defaultdict(int)
    filtered = []

    for result in results:
        source_url = result["source_url"]
        if seen[source_url] < max_per_source:
            filtered.append(result)
            seen[source_url] += 1

    return filtered


def select_adaptive_results(
    results: list,
    target_services: list[str],
    min_results: int = 5,
    per_service: int = 2,
    max_per_source: int = 2,
) -> list:
    if not target_services:
        return filter_diversity(results, max_per_source)[:min_results]

    desired_results = max(min_results, len(target_services) * per_service)
    coverage = defaultdict(int)
    source_counts = defaultdict(int)
    selected = []
    selected_ids = set()

    def add(result: dict) -> bool:
        chunk_id = result["chunk_id"]
        source_url = result["source_url"]
        if chunk_id in selected_ids or source_counts[source_url] >= max_per_source:
            return False

        selected.append(result)
        selected_ids.add(chunk_id)
        source_counts[source_url] += 1
        for service in target_services:
            if service in result["services"]:
                coverage[service] += 1
        return True

    for _ in range(per_service):
        for service in target_services:
            if coverage[service] >= per_service:
                continue
            service_results = [
                result for result in results if service in result["services"]
            ]
            preferred = [
                result
                for result in service_results
                if source_counts[result["source_url"]] == 0
            ]
            for result in (*preferred, *service_results):
                if add(result):
                    break

    for result in results:
        if len(selected) >= desired_results:
            break
        add(result)

    return selected


def matches_scope(chunk: dict, service: str | None, category: str | None) -> bool:
    return (
        (service is None or service in chunk["services"])
        and (category is None or category in chunk["categories"])
    )
