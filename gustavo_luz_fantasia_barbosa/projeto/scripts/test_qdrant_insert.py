import random
import requests

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "nvidia_knowledge_base"

def generate_fake_vector(size: int = 1536):
    return [random.random() for _ in range(size)]

def main():
    fake_vector = generate_fake_vector()

    payload = {
        "points": [
            {
                "id": 1,
                "vector": fake_vector,
                "payload": {
                    "product_name": "NVIDIA NIM",
                    "category": "model_deployment",
                    "source_type": "test",
                    "source_url": "https://www.nvidia.com/en-us/ai-data-science/products/nim-microservices/",
                    "chunk_text": "NVIDIA NIM provides optimized inference microservices for deploying AI models in production."
                }
            }
        ]
    }

    response = requests.put(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points",
        json=payload,
        timeout=10
    )

    print("Status code:", response.status_code)
    print("Resposta:")
    print(response.json())

if __name__ == "__main__":
    main()
