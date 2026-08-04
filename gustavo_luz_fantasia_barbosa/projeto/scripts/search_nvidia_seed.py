from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = PROJECT_ROOT / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

from app.config import get_settings
from app.rag.embeddings import create_embedding_provider
from app.rag.vector_store import QdrantHttpClient


def main():
    query = " ".join(sys.argv[1:]) or "latencia e custo de inferencia para LLM"
    settings = get_settings()
    vector_store = QdrantHttpClient(
        base_url=settings.qdrant_url,
        vector_size=settings.vector_size,
        distance=settings.vector_distance,
    )
    embedder = create_embedding_provider(settings)

    results = vector_store.search(
        collection_name=settings.nvidia_collection,
        vector=embedder.embed(query),
        limit=5,
    )

    print(f"Consulta: {query}")
    for index, result in enumerate(results, start=1):
        payload = result.get("payload") or {}
        print()
        print(f"{index}. {payload.get('product_name')} | score={result.get('score')}")
        print(payload.get("summary"))
        print(payload.get("source_url"))


if __name__ == "__main__":
    main()
