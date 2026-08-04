from typing import Dict, List

from .config import CHROMA_PERSIST_DIR


def init_chroma(persist_dir: str = CHROMA_PERSIST_DIR):
    """
    Inicializa e retorna um cliente Chroma com persistencia local.
    """
    try:
        import chromadb
    except Exception as exc:
        raise RuntimeError("chromadb e necessario: pip install chromadb") from exc

    return chromadb.PersistentClient(path=str(persist_dir))


def get_or_create_collection(client, collection_name: str):
    return client.get_or_create_collection(name=collection_name)


def reset_collection(client, collection_name: str):
    """
    Remove e recria a colecao para reindexacao limpa.
    """
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass
    return client.get_or_create_collection(name=collection_name)


def upsert_documents(client, collection_name: str, docs: List[Dict]):
    """
    Insere ou atualiza documentos em uma colecao Chroma.
    Cada item deve conter:
    - id
    - text
    - embedding
    - meta (opcional)
    """
    coll = get_or_create_collection(client, collection_name)
    ids = [d["id"] for d in docs]
    texts = [d["text"] for d in docs]
    metadatas = [d.get("meta", {}) for d in docs]
    embeddings = [d["embedding"] for d in docs]

    coll.upsert(
        ids=ids,
        documents=texts,
        metadatas=metadatas,
        embeddings=embeddings,
    )
