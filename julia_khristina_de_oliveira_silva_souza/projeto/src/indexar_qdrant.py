# indexar_qdrant.py
import json
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

with open("chunks_with_embeddings.json", "r", encoding="utf-8") as f:
    chunks = json.load(f)

client = QdrantClient(path="./qdrant_local")  # local em disco, sem precisar de servidor

DIM = len(chunks[0]["embedding"])

client.recreate_collection(
    collection_name="nvidia_kb",
    vectors_config=VectorParams(size=DIM, distance=Distance.COSINE)
)

points = [
    PointStruct(
        id=chunk["id"],
        vector=chunk["embedding"],
        payload={
            "tech": chunk["tech"],
            "category": chunk["category"],
            "url": chunk["url"],
            "text": chunk["text"]
        }
    )
    for chunk in chunks
]

client.upsert(collection_name="nvidia_kb", points=points)
print(f"Indexado: {len(points)} chunks no Qdrant")