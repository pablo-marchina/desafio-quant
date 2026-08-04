"""Product RAG module with lazy public exports."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS: dict[str, str] = {
    "build_supporting_contexts": "src.rag.context_packing",
    "pack_contexts": "src.rag.context_packing",
    "CounterEvidenceAssessment": "src.rag.counter_evidence",
    "CounterEvidenceConfig": "src.rag.counter_evidence",
    "CounterEvidenceRecord": "src.rag.counter_evidence",
    "retrieve_counter_evidence": "src.rag.counter_evidence",
    "EmbeddingProvider": "src.rag.embeddings",
    "SentenceTransformerProvider": "src.rag.embeddings",
    "EvidenceGraphConfig": "src.rag.evidence_graph",
    "EvidenceGraphEdge": "src.rag.evidence_graph",
    "EvidenceGraphNode": "src.rag.evidence_graph",
    "EvidenceGraphResult": "src.rag.evidence_graph",
    "build_evidence_graph": "src.rag.evidence_graph",
    "graph_lineage_summary": "src.rag.evidence_graph",
    "EvidenceSufficiencyAssessment": "src.rag.evidence_sufficiency",
    "EvidenceSufficiencyConfig": "src.rag.evidence_sufficiency",
    "assess_evidence_sufficiency": "src.rag.evidence_sufficiency",
    "hybrid_retrieve": "src.rag.hybrid_retrieval",
    "load_and_chunk_corpus": "src.rag.ingestion",
    "load_sources": "src.rag.ingestion",
    "CORPUS_VERSION": "src.rag.ingestion_pipeline",
    "REQUIRED_PAYLOAD_FIELDS": "src.rag.ingestion_pipeline",
    "CorpusReadinessResult": "src.rag.ingestion_pipeline",
    "IngestionReport": "src.rag.ingestion_pipeline",
    "check_corpus_readiness": "src.rag.ingestion_pipeline",
    "run_ingestion_pipeline": "src.rag.ingestion_pipeline",
    "validate_payload_schema": "src.rag.ingestion_pipeline",
    "PlaybookRetriever": "src.rag.playbook_retriever",
    "QdrantConfig": "src.rag.qdrant_store",
    "QdrantConnectionError": "src.rag.qdrant_store",
    "QdrantStore": "src.rag.qdrant_store",
    "build_qdrant_store": "src.rag.qdrant_store",
    "QueryRewriteConfig": "src.rag.query_rewriting",
    "build_query_variants": "src.rag.query_rewriting",
    "retrieve_multi_query": "src.rag.query_rewriting",
    "run_rag_pipeline": "src.rag.rag_pipeline",
    "QdrantRagService": "src.rag.rag_service_factory",
    "build_qdrant_rag_service": "src.rag.rag_service_factory",
    "rerank_contexts": "src.rag.reranking",
    "ChunkIndex": "src.rag.retrieval",
    "build_default_index": "src.rag.retrieval",
    "semantic_retrieve": "src.rag.semantic_retrieval",
    "RankedSourceContext": "src.rag.source_quality",
    "SourceQualityFeatures": "src.rag.source_quality",
    "SourceQualityRankingConfig": "src.rag.source_quality",
    "rank_contexts_by_source_quality": "src.rag.source_quality",
    "score_source_quality": "src.rag.source_quality",
    "InMemoryVectorStore": "src.rag.vector_store",
    "VectorEntry": "src.rag.vector_store",
    "VectorStore": "src.rag.vector_store",
    "DroppedContext": "src.rag.schemas",
    "PackedContext": "src.rag.schemas",
    "PackingConfig": "src.rag.schemas",
    "PackingResult": "src.rag.schemas",
    "PlaybookRetrievalResult": "src.rag.schemas",
    "RagChunk": "src.rag.schemas",
    "RagDocument": "src.rag.schemas",
    "RagPipelineOutput": "src.rag.schemas",
    "RagSource": "src.rag.schemas",
    "RerankingConfig": "src.rag.schemas",
    "RetrievalQuery": "src.rag.schemas",
    "RetrievedContext": "src.rag.schemas",
    "SupportingNvidiaContext": "src.rag.schemas",
    "TechniquesConfig": "src.rag.schemas",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module 'src.rag' has no attribute {name!r}")
    module = import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value
