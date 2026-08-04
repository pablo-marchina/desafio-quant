from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator


load_dotenv(Path(__file__).resolve().parents[2] / ".env")


class RAGConfig(BaseModel):
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    collection_name: str = "nvidia_knowledge"
    embedding_provider: str = "fastembed"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    openai_embedding_dimensions: int = 1536
    sparse_model: str = "Qdrant/bm25"
    top_k: int = Field(default=20, ge=5, le=100)
    top_n: int = Field(default=5, ge=1, le=20)
    generator_provider: str = "deterministic"
    generator_model: str = "gpt-4o"
    reranker_provider: str = "lexical"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"

    @classmethod
    def from_env(cls) -> "RAGConfig":
        return cls(
            qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            qdrant_api_key=os.getenv("QDRANT_API_KEY") or None,
            collection_name=os.getenv("QDRANT_COLLECTION", "nvidia_knowledge"),
            embedding_provider=os.getenv("EMBEDDING_PROVIDER", "fastembed"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"),
            openai_embedding_dimensions=int(os.getenv("OPENAI_EMBEDDING_DIMENSIONS", "1536")),
            sparse_model=os.getenv("SPARSE_EMBEDDING_MODEL", "Qdrant/bm25"),
            top_k=int(os.getenv("RAG_TOP_K", "20")),
            top_n=int(os.getenv("RAG_TOP_N", "5")),
            generator_provider=os.getenv("RAG_GENERATOR_PROVIDER", "deterministic"),
            generator_model=os.getenv("RAG_GENERATOR_MODEL", "gpt-4o"),
            reranker_provider=os.getenv("RERANKER_PROVIDER", "lexical"),
            reranker_model=os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"),
        )

    @field_validator("embedding_provider")
    @classmethod
    def validate_embedding_provider(cls, value: str) -> str:
        if value not in {"fastembed", "openai"}:
            raise ValueError("EMBEDDING_PROVIDER deve ser fastembed ou openai")
        return value

    @field_validator("generator_provider")
    @classmethod
    def validate_generator_provider(cls, value: str) -> str:
        if value not in {"deterministic", "openai"}:
            raise ValueError("RAG_GENERATOR_PROVIDER deve ser deterministic ou openai")
        return value
