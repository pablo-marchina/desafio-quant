from typing import Any
from .config import RETRIEVAL_TOPK

def retrieve(client, collection_name: str, query_embedding: Any, top_k: int = RETRIEVAL_TOPK):
    """
    Executa busca por similaridade vetorial na coleção Chroma.
    Retorna o dicionário de resultados que inclui ids, documents, metadatas e distances.
    """
    coll = client.get_collection(name=collection_name)
    results = coll.query(query_embeddings=[query_embedding], n_results=top_k)
    return results