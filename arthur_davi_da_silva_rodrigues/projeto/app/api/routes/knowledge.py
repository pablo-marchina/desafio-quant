from fastapi import APIRouter

from app.api.schemas import (
    KnowledgeIngestResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResultResponse,
    NvidiaTechnologyResponse,
)
from app.rag.catalog import NVIDIA_TECHNOLOGY_CATALOG
from app.rag.ingestion import prepare_seed_knowledge_documents
from app.rag.search import search_technology_catalog

router = APIRouter()


@router.get("/technologies")
def list_technologies() -> list[NvidiaTechnologyResponse]:
    return [
        NvidiaTechnologyResponse(
            name=catalog_item.name,
            category=catalog_item.category,
            description=catalog_item.description,
            source_url=catalog_item.source_url,
        )
        for catalog_item in NVIDIA_TECHNOLOGY_CATALOG
    ]


@router.post("/search")
def search_knowledge(request: KnowledgeSearchRequest) -> list[KnowledgeSearchResultResponse]:
    return [
        KnowledgeSearchResultResponse(
            name=result.name,
            category=result.category,
            description=result.description,
            source_url=result.source_url,
            score=result.score,
            matched_keywords=result.matched_keywords,
        )
        for result in search_technology_catalog(request.query, request.limit)
    ]


@router.post("/ingest", status_code=202)
def ingest_knowledge() -> KnowledgeIngestResponse:
    prepared_documents = prepare_seed_knowledge_documents()
    chunk_count = sum(len(document.chunks) for document in prepared_documents)

    return KnowledgeIngestResponse(
        status="prepared",
        document_count=len(prepared_documents),
        chunk_count=chunk_count,
    )
