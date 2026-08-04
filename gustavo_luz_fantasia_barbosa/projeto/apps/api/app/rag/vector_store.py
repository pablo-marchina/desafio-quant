from typing import Any
import requests


class QdrantHttpClient:
    def __init__(self, base_url: str, vector_size: int, distance: str = "Cosine"):
        self.base_url = base_url.rstrip("/")
        self.vector_size = vector_size
        self.distance = distance

    def health(self) -> dict[str, Any]:
        response = requests.get(self.base_url, timeout=5)
        response.raise_for_status()
        return response.json()

    def collection_exists(self, collection_name: str) -> bool:
        response = requests.get(
            f"{self.base_url}/collections/{collection_name}",
            timeout=10,
        )
        if response.status_code == 404:
            return False
        response.raise_for_status()
        return True

    def collection_vector_config(self, collection_name: str) -> dict[str, Any] | None:
        response = requests.get(
            f"{self.base_url}/collections/{collection_name}",
            timeout=10,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        vectors = (
            response.json()
            .get("result", {})
            .get("config", {})
            .get("params", {})
            .get("vectors", {})
        )
        return vectors if isinstance(vectors, dict) else None

    def ensure_collection(self, collection_name: str, recreate: bool = False) -> None:
        if recreate:
            requests.delete(f"{self.base_url}/collections/{collection_name}", timeout=10)
        else:
            vector_config = self.collection_vector_config(collection_name)
            if vector_config:
                current_size = int(vector_config.get("size") or 0)
                current_distance = str(vector_config.get("distance") or "")
                if (
                    current_size == self.vector_size
                    and current_distance.lower() == self.distance.lower()
                ):
                    return
                requests.delete(
                    f"{self.base_url}/collections/{collection_name}",
                    timeout=10,
                )

        payload = {
            "vectors": {
                "size": self.vector_size,
                "distance": self.distance,
            }
        }
        response = requests.put(
            f"{self.base_url}/collections/{collection_name}",
            json=payload,
            timeout=10,
        )
        response.raise_for_status()

    def upsert_points(self, collection_name: str, points: list[dict[str, Any]]) -> None:
        if not points:
            return

        response = requests.put(
            f"{self.base_url}/collections/{collection_name}/points",
            json={"points": points},
            timeout=30,
        )
        response.raise_for_status()

    def search(
        self,
        collection_name: str,
        vector: list[float],
        limit: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        query_payload: dict[str, Any] = {
            "query": vector,
            "limit": limit,
            "with_payload": True,
        }

        if filters:
            query_payload["filter"] = {
                "must": [
                    {"key": key, "match": {"value": value}}
                    for key, value in filters.items()
                    if value is not None
                ]
            }

        response = requests.post(
            f"{self.base_url}/collections/{collection_name}/points/query",
            json=query_payload,
            timeout=20,
        )
        if response.status_code == 404:
            legacy_payload = dict(query_payload)
            legacy_payload["vector"] = legacy_payload.pop("query")
            response = requests.post(
                f"{self.base_url}/collections/{collection_name}/points/search",
                json=legacy_payload,
                timeout=20,
            )

        response.raise_for_status()
        result = response.json().get("result", [])
        if isinstance(result, dict):
            return result.get("points", [])
        return result
