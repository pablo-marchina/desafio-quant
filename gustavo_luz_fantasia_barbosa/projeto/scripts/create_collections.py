import requests

QDRANT_URL = "http://localhost:6333"

COLLECTIONS = [
    "nvidia_knowledge_base",
    "startup_evidence",
]

VECTOR_SIZE = 1536
DISTANCE = "Cosine"

def create_collection(collection_name: str):
    url = f"{QDRANT_URL}/collections/{collection_name}"

    payload = {
        "vectors": {
            "size": VECTOR_SIZE,
            "distance": DISTANCE
        }
    }

    response = requests.put(url, json=payload, timeout=10)

    if response.status_code in [200, 201]:
        print(f"Collection criada ou atualizada: {collection_name}")
        print(response.json())
    else:
        print(f"Erro ao criar collection: {collection_name}")
        print(response.status_code)
        print(response.text)

def list_collections():
    response = requests.get(f"{QDRANT_URL}/collections", timeout=10)
    response.raise_for_status()

    print("Collections existentes:")
    print(response.json())

def main():
    for collection_name in COLLECTIONS:
        create_collection(collection_name)

    print()
    list_collections()

if __name__ == "__main__":
    main()
