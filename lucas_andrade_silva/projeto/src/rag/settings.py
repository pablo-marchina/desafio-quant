import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
DOCUMENTS_PATH = DATA_DIR / "raw" / "documents.json"
SCRAPE_FAILURES_PATH = DATA_DIR / "raw" / "scrape_failures.json"
CHUNKS_PATH = DATA_DIR / "processed" / "chunks.json"
EMBEDDINGS_PATH = DATA_DIR / "processed" / "embeddings.npy"
EMBEDDINGS_STATE_PATH = DATA_DIR / "processed" / "embeddings_state.json"

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_TIMEOUT = int(os.getenv("QDRANT_TIMEOUT", "5"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "nvidia_services")

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
VECTOR_SIZE = 1024


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} nao foi definida no arquivo .env")
    return value
