"""BM25 runtime technique wrapper.

The official RAG service uses ``SparseRetriever`` directly for BM25 retrieval.
This class exists for the technique runner so BM25 is also visible as an active
runtime technique in the product graph.
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext, RetrievalQuery
from src.rag.retrieval import ChunkIndex
from src.rag.sparse_retrieval import SparseRetriever


class Bm25:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query = kwargs.get("retrieval_query") or kwargs.get("query")
        chunk_index = kwargs.get("chunk_index")
        if not isinstance(query, RetrievalQuery) or not isinstance(chunk_index, ChunkIndex):
            return contexts
        bm25_contexts = SparseRetriever(chunk_index).retrieve(query, top_k=int(kwargs.get("top_k", 10)))
        seen = {ctx.chunk_id for ctx in contexts}
        return contexts + [ctx for ctx in bm25_contexts if ctx.chunk_id not in seen]
