# trabalhar com caminhos de arquivos e diretórios
from pathlib import Path # orientada a objetos
import os # funcoes

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]
DATA_PROCESSED = ROOT / "data" / "processed"
DATA_RAW = ROOT / "data" / "raw"
NVIDIA_KB_RAW_DIR = DATA_RAW / "nvidia_kb"
NVIDIA_KB_PROCESSED_DIR = DATA_PROCESSED / "nvidia_kb"
NVIDIA_KB_CHUNKS_DIR = DATA_PROCESSED / "nvidia_kb_chunks"
HF_CACHE_DIR = os.environ.get("HF_HOME", str(ROOT / "data" / "hf_cache"))

# Modelo de embeddings (HuggingFace / sentence-transformers)
EMBEDDING_MODEL = os.environ.get("RAG_EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")
CHROMA_PERSIST_DIR = os.environ.get("CHROMA_PERSIST_DIR", str(ROOT / "data" / "chroma_db"))
RAG_EMBEDDINGS_LOCAL_ONLY = os.environ.get("RAG_EMBEDDINGS_LOCAL_ONLY", "true").strip().lower() in {"1", "true", "yes", "on"}

# OpenRouter / LLM
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_BASE = os.environ.get("OPENROUTER_BASE", "https://api.openrouter.ai")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")

# Parâmetros de chunking e recuperação
## Vai dividir os "textos" e para que sejam unidos tem esse overlap
CHUNK_SIZE = int(os.environ.get("RAG_CHUNK_SIZE", 500))
CHUNK_OVERLAP = int(os.environ.get("RAG_CHUNK_OVERLAP", 100))
RETRIEVAL_TOPK = int(os.environ.get("RAG_RETRIEVAL_TOPK", 50))
RERANK_TOPK = int(os.environ.get("RAG_RERANK_TOPK", 5))
