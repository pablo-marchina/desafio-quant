from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = PROJECT_ROOT / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

from app.config import get_settings
from app.rag.embeddings import create_embedding_provider
from app.rag.ingest import ingest_nvidia_official_pages
from app.rag.vector_store import QdrantHttpClient


def main():
    settings = get_settings()
    vector_store = QdrantHttpClient(
        base_url=settings.qdrant_url,
        vector_size=settings.vector_size,
        distance=settings.vector_distance,
    )
    embedder = create_embedding_provider(settings)

    result = ingest_nvidia_official_pages(
        vector_store=vector_store,
        embedder=embedder,
        collection_name=settings.nvidia_collection,
        reset_collection=True,
    )

    print("Fontes oficiais NVIDIA ingeridas.")
    print(f"Collection: {result['collection_name']}")
    print(f"Fontes coletadas: {result['documents']}")
    print(f"Chunks: {result['chunks']}")
    print(f"Coletado em: {result['collected_at']}")
    print()

    for source in result["sources"]:
        print(
            f"- {source['product_name']}: {source['status']} | "
            f"chunks={source['chunks']} | chars={source['characters']}"
        )
        if source["error"]:
            print(f"  erro: {source['error']}")


if __name__ == "__main__":
    main()
