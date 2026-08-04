import json
import logging
from pathlib import Path
from typing import Dict, List

from .config import NVIDIA_KB_CHUNKS_DIR
from .embeddings import EmbeddingClient
from .store import init_chroma, reset_collection, upsert_documents

logger = logging.getLogger(__name__)

DEFAULT_COLLECTION = "nvidia_kb"
DEFAULT_CHUNKS_PATH = NVIDIA_KB_CHUNKS_DIR / "chunks.json"


def load_chunk_documents(path: Path = DEFAULT_CHUNKS_PATH) -> List[Dict]:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo de chunks nao encontrado: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("O arquivo de chunks deve conter uma lista de objetos")
    return data


def prepare_documents_for_indexing(chunks: List[Dict]) -> List[Dict]:
    texts = [chunk.get("texto_chunk", "") for chunk in chunks]
    emb = EmbeddingClient()
    vectors = emb.embed(texts)

    prepared: List[Dict] = []
    for chunk, vector in zip(chunks, vectors):
        prepared.append(
            {
                "id": chunk["id"],
                "text": chunk["texto_chunk"],
                "embedding": vector,
                "meta": {
                    "document_id": chunk.get("document_id"),
                    "titulo": chunk.get("titulo"),
                    "nome_produto": chunk.get("nome_produto"),
                    "categoria": chunk.get("categoria"),
                    "chunk_index": chunk.get("chunk_index"),
                    "url_pesquisa": chunk.get("url_pesquisa"),
                    "tags": ", ".join(chunk.get("tags", [])),
                    "caso_uso": ", ".join(chunk.get("caso_uso", [])),
                    "fonte_tipo": chunk.get("fonte_tipo"),
                    "coletado_em": chunk.get("coletado_em"),
                },
            }
        )

    return prepared


def index_chunks(
    chunks_path: Path = DEFAULT_CHUNKS_PATH,
    collection_name: str = DEFAULT_COLLECTION,
) -> int:
    chunks = load_chunk_documents(chunks_path)
    docs = prepare_documents_for_indexing(chunks)

    client = init_chroma()
    reset_collection(client, collection_name)
    upsert_documents(client, collection_name, docs)

    logger.info("Colecao %s indexada com %d chunks", collection_name, len(docs))
    return len(docs)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    total = index_chunks()
    print(f"{total} chunks indexados no Chroma em '{DEFAULT_COLLECTION}'")
