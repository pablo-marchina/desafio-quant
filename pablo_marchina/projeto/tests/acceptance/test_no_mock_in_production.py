"""Guard: production RAG must not use mock or in-memory providers."""


def test_product_rag_factory_uses_real_provider() -> None:
    """Verify production RAG factory references real embeddings only."""
    import inspect

    import src.rag.rag_service_factory as rag_factory

    source = inspect.getsource(rag_factory)
    assert "SentenceTransformerProvider" in source
    assert "MockEmbeddingProvider" not in source


def test_sentence_transformer_provider_raises_without_sentence_transformers() -> None:
    """When sentence-transformers is not installed, local backend raises ImportError."""
    import sys

    orig = sys.modules.get("sentence_transformers")
    sys.modules["sentence_transformers"] = None  # type: ignore[assignment]
    try:
        from src.rag.embeddings import SentenceTransformerProvider as STP

        try:
            STP()
            raise AssertionError("Expected ImportError")
        except ImportError:
            pass
    finally:
        if orig is not None:
            sys.modules["sentence_transformers"] = orig
        else:
            sys.modules.pop("sentence_transformers", None)


def test_in_memory_vector_store_is_blocked_in_product(monkeypatch) -> None:
    """In-memory vector store is allowed for unit tests only."""
    monkeypatch.setenv("APP_MODE", "product")
    monkeypatch.setenv("RAG_VECTOR_BACKEND", "in_memory")

    from src.rag.vector_store import InMemoryVectorStore

    try:
        InMemoryVectorStore()
        raise AssertionError("Expected RuntimeError")
    except RuntimeError as exc:
        assert "FORBIDDEN in production" in str(exc)


def test_product_runtime_uses_single_langgraph_pipeline() -> None:
    """ProductService must not default to the legacy pipeline with stubs."""
    from scripts.check_single_runtime_pipeline import validate_single_runtime_pipeline

    failures = validate_single_runtime_pipeline()
    assert failures == []
