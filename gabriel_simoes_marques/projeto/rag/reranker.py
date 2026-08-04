from graphiti_core.cross_encoder.client import CrossEncoderClient
from sentence_transformers import CrossEncoder


class LocalReranker(CrossEncoderClient):
    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3"):
        self.model = CrossEncoder(model_name)

    async def rank(self, query: str, passages: list[str]) -> list[tuple[str, float]]:
        pairs = [[query, p] for p in passages]
        scores = self.model.predict(pairs)
        ranked = sorted(zip(passages, scores), key=lambda x: x[1], reverse=True)
        return [(p, float(s)) for p, s in ranked]