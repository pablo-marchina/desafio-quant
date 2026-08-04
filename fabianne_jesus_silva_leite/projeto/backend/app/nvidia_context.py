from app.rag.schemas import (
    NvidiaContextResponse,
    NvidiaContextTechnology,
    NvidiaRagQueryRequest,
    ResearchWithNvidiaContextResponse,
)
from app.rag.service import run_nvidia_rag
from app.schemas import ResearchResponse


MAX_RESULTS_PER_QUERY = 3
MAX_EVIDENCES_PER_TECHNOLOGY = 2
MAX_TECHNOLOGIES = 6


def has_profile_evidence(
    research: ResearchResponse,
    category: str,
) -> bool:
    return bool(
        getattr(
            research.profile,
            category,
            [],
        )
    )


def has_unknown_gap(
    research: ResearchResponse,
    category: str,
) -> bool:
    return any(
        gap.category == category
        and gap.status == "DESCONHECIDA"
        for gap in research.gaps
    )


def build_nvidia_queries(
    research: ResearchResponse,
) -> list[str]:
    queries = []

    has_ai_product = has_profile_evidence(
        research,
        "ai_product",
    )

    has_scale = has_profile_evidence(
        research,
        "scale_traction",
    )

    has_governance = has_profile_evidence(
        research,
        "governance_security",
    )

    has_documents = (
        has_profile_evidence(
            research,
            "proprietary_data",
        )
        and has_profile_evidence(
            research,
            "workflow_depth",
        )
    )

    has_inference_gap = has_unknown_gap(
        research,
        "model_and_serving",
    )

    if has_ai_product and (
        has_scale or has_inference_gap
    ):
        queries.append(
            "NVIDIA technologies for LLM inference optimization, "
            "latency reduction, throughput, batching, serving and "
            "high token volume in production."
        )

    if has_governance:
        queries.append(
            "NVIDIA technologies for programmable guardrails, "
            "validation, safety, governance and controls in "
            "LLM agents used in sensitive workflows."
        )

    if has_documents:
        queries.append(
            "NVIDIA technologies for RAG over proprietary documents, "
            "semantic retrieval, embeddings and reranking in "
            "enterprise workflows."
        )

    if not queries:
        queries.append(
            "NVIDIA technologies for deploying and operating "
            "AI applications in production."
        )

    return queries


def add_result_to_technology(
    technologies_by_id: dict[str, NvidiaContextTechnology],
    query: str,
    result,
) -> None:
    technology = technologies_by_id.get(
        result.technology_id
    )

    if technology is None:
        technologies_by_id[result.technology_id] = (
            NvidiaContextTechnology(
                technology_id=result.technology_id,
                technology_name=result.technology_name,
                why_retrieved=[query],
                evidences=[result],
            )
        )
        return

    if query not in technology.why_retrieved:
        technology.why_retrieved.append(query)

    already_added = any(
        evidence.source_url == result.source_url
        and evidence.text == result.text
        for evidence in technology.evidences
    )

    if (
        not already_added
        and len(technology.evidences)
        < MAX_EVIDENCES_PER_TECHNOLOGY
    ):
        technology.evidences.append(result)


def build_nvidia_context(
    research: ResearchResponse,
) -> NvidiaContextResponse:
    generated_queries = build_nvidia_queries(research)

    technologies_by_id: dict[
        str,
        NvidiaContextTechnology,
    ] = {}

    for query in generated_queries:
        rag_response = run_nvidia_rag(
            NvidiaRagQueryRequest(
                query=query,
                top_k=MAX_RESULTS_PER_QUERY,
            )
        )

        for result in rag_response.results:
            add_result_to_technology(
                technologies_by_id=technologies_by_id,
                query=query,
                result=result,
            )

    technologies = sorted(
        technologies_by_id.values(),
        key=lambda technology: max(
            evidence.rerank_score
            for evidence in technology.evidences
        ),
        reverse=True,
    )[:MAX_TECHNOLOGIES]

    return NvidiaContextResponse(
        generated_queries=generated_queries,
        technologies=technologies,
    )


def build_research_with_nvidia_context(
    research: ResearchResponse,
) -> ResearchWithNvidiaContextResponse:
    return ResearchWithNvidiaContextResponse(
        research=research,
        nvidia_context=build_nvidia_context(research),
    )