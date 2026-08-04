from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = PROJECT_ROOT / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

from app.config import get_settings
from app.rag.embeddings import create_embedding_provider


def main():
    settings = get_settings()
    try:
        embedder = create_embedding_provider(settings)
        vector = embedder.embed("teste de embedding para RAG NVIDIA")
    except Exception as error:
        print("Erro ao validar provider de embeddings:")
        print(error)
        return 1

    print(f"Provider: {settings.embedding_provider}")
    print(f"Modelo OpenAI: {settings.openai_embedding_model}")
    print(f"Vector size configurado: {settings.vector_size}")
    print(f"Vector size retornado: {len(vector)}")
    print(f"Primeiros valores: {vector[:5]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
