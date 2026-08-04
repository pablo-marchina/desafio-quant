import hashlib
import json
import uuid

import numpy as np
import torch
from FlagEmbedding import BGEM3FlagModel
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PayloadSchemaType, PointStruct, VectorParams

from rag.settings import (
    CHUNKS_PATH,
    EMBEDDING_MODEL,
    EMBEDDINGS_PATH,
    EMBEDDINGS_STATE_PATH,
    QDRANT_COLLECTION,
    QDRANT_HOST,
    QDRANT_PORT,
    QDRANT_TIMEOUT,
    VECTOR_SIZE,
)

BATCH_SIZE = 16
EMBEDDING_BLOCK_SIZE = 256
UPLOAD_BATCH_SIZE = 128
POINT_NAMESPACE = uuid.UUID("72892895-1e4c-471c-8b8a-c933a4ebadad")


def point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(POINT_NAMESPACE, chunk_id))


def save_state(signature: str, completed: int, total: int) -> None:
    with EMBEDDINGS_STATE_PATH.open("w", encoding="utf-8") as file:
        json.dump(
            {"signature": signature, "completed": completed, "total": total},
            file,
            indent=2,
        )


def generate_embeddings(model, chunks: list[dict]) -> np.memmap:
    signature = hashlib.sha256(
        "\n".join(chunk["chunk_id"] for chunk in chunks).encode("utf-8")
    ).hexdigest()
    state = {}
    if EMBEDDINGS_STATE_PATH.exists():
        with EMBEDDINGS_STATE_PATH.open("r", encoding="utf-8") as file:
            state = json.load(file)

    can_resume = (
        EMBEDDINGS_PATH.exists()
        and state.get("signature") == signature
        and state.get("total") == len(chunks)
    )
    if can_resume:
        completed = state["completed"]
        vectors = np.lib.format.open_memmap(EMBEDDINGS_PATH, mode="r+")
        print(f"Retomando embeddings em {completed}/{len(chunks)}.")
    else:
        EMBEDDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        vectors = np.lib.format.open_memmap(
            EMBEDDINGS_PATH,
            mode="w+",
            dtype=np.float32,
            shape=(len(chunks), VECTOR_SIZE),
        )
        completed = 0
        save_state(signature, completed, len(chunks))

    for start in range(completed, len(chunks), EMBEDDING_BLOCK_SIZE):
        end = min(start + EMBEDDING_BLOCK_SIZE, len(chunks))
        output = model.encode(
            [chunk["text"] for chunk in chunks[start:end]],
            batch_size=BATCH_SIZE,
            max_length=512,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        vectors[start:end] = output["dense_vecs"]
        vectors.flush()
        save_state(signature, end, len(chunks))
        print(f"  Embeddings: {end}/{len(chunks)}")

    return vectors


def main() -> None:
    with CHUNKS_PATH.open("r", encoding="utf-8") as file:
        chunks = json.load(file)

    if not chunks:
        raise RuntimeError(
            "Nenhum chunk encontrado. Execute rag.ingestion.chunk."
        )

    client_qdrant = QdrantClient(
        host=QDRANT_HOST,
        port=QDRANT_PORT,
        timeout=QDRANT_TIMEOUT,
    )
    try:
        client_qdrant.get_collections()
    except Exception as error:
        raise RuntimeError(
            f"Nao foi possivel conectar ao Qdrant em {QDRANT_HOST}:{QDRANT_PORT}. "
            "Inicie com 'docker compose up -d'."
        ) from error

    use_fp16 = torch.cuda.is_available()
    print(f"Carregando {EMBEDDING_MODEL} (FP16={use_fp16})...")
    model = BGEM3FlagModel(EMBEDDING_MODEL, use_fp16=use_fp16)

    print(f"Gerando embeddings para {len(chunks)} chunks...")
    vectors = generate_embeddings(model, chunks)

    if client_qdrant.collection_exists(QDRANT_COLLECTION):
        client_qdrant.delete_collection(QDRANT_COLLECTION)

    client_qdrant.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )
    for field_name in ("services", "categories", "source_url"):
        client_qdrant.create_payload_index(
            collection_name=QDRANT_COLLECTION,
            field_name=field_name,
            field_schema=PayloadSchemaType.KEYWORD,
        )
    print(f"Collection '{QDRANT_COLLECTION}' criada.")

    for batch_start in range(0, len(chunks), UPLOAD_BATCH_SIZE):
        batch = chunks[batch_start : batch_start + UPLOAD_BATCH_SIZE]
        vector_batch = vectors[batch_start : batch_start + UPLOAD_BATCH_SIZE]

        points = [
            PointStruct(
                id=point_id(chunk["chunk_id"]),
                vector=vector.tolist(),
                payload={
                    "text": chunk["text"],
                    "source_url": chunk["source_url"],
                    "chunk_id": chunk["chunk_id"],
                    "scraped_at": chunk["scraped_at"],
                    "scraper_source": chunk["scraper_source"],
                    "services": chunk["services"],
                    "categories": chunk["categories"],
                },
            )
            for chunk, vector in zip(batch, vector_batch)
        ]
        client_qdrant.upsert(collection_name=QDRANT_COLLECTION, points=points)
        print(
            f"  Armazenados: "
            f"{min(batch_start + UPLOAD_BATCH_SIZE, len(chunks))}/{len(chunks)}"
        )

    info = client_qdrant.get_collection(QDRANT_COLLECTION)
    print(f"\nTotal armazenado: {info.points_count} chunks no Qdrant.")


if __name__ == "__main__":
    main()
