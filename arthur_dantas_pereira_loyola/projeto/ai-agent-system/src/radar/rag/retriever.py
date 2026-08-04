from __future__ import annotations

from radar.rag.knowledge_base import get_seed_chunks
from radar.rag.vector_store import VectorStore

_store: VectorStore | None = None
_seeded: bool = False


def get_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store


def ensure_seeded() -> int:
    global _seeded
    if _seeded:
        return get_store().count()

    store = get_store()
    chunks = get_seed_chunks()
    inserted = store.insert(chunks)
    _seeded = True
    return inserted


def retrieve(query: str, top_k: int = 5) -> list[dict]:
    ensure_seeded()
    return get_store().search(query, top_k=top_k)


def reset() -> None:
    global _store, _seeded
    if _store is not None:
        _store.clear()
    _store = None
    _seeded = False
