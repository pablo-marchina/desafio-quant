import random
import requests

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "nvidia_knowledge_base"

def generate_fake_vector(size: int = 1536):
    return [random.random() for _ in range(size)]

def main():
    query_vector = generate_fake_vector()

    payload = {
        "vector": query_vector,
        "limit": 3,
        "with_payload": True
    }

    response = requests.post(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/search",
        json=payload,
        timeout=10
    )

    print("Status code:", response.status_code)
    print("Resposta:")
    print(response.json())

if __name__ == "__main__":
    main()
