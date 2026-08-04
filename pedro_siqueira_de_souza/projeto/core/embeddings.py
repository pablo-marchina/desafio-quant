"""Abstração da camada de embeddings (RAG — Entregável 3).

Espelha a decisão do `core/llm.py`: em vez de instanciar `OpenAIEmbeddings(...)`
espalhado pelo código do RAG, todos pedem o modelo de embeddings aqui. Assim o
indexador e o retriever usam EXATAMENTE o mesmo modelo (essencial — vetores de
modelos diferentes não são comparáveis) e trocar de modelo é mudar uma variável
de ambiente (`EMBEDDING_MODEL`).

Decisão didática: mantemos a interface mínima do LangChain (`embed_documents` /
`embed_query`) à mostra, em vez de esconder atrás de um wrapper próprio — é essa
interface que o `rag/index.py` e o `rag/retrieve.py` consomem.
"""
from functools import lru_cache

from langchain_core.embeddings import Embeddings

from core.config import settings


@lru_cache
def get_embeddings() -> Embeddings:
    """Retorna o modelo de embeddings configurado via `EMBEDDING_MODEL`.

    Usa a chave da OpenAI (mesma do LLM). Falha cedo e com mensagem clara se a
    chave faltar — "tratamento de erro explícito".
    """
    if not settings.openai_api_key:
        raise RuntimeError(
            "Embeddings exigem OPENAI_API_KEY, mas está vazio. Preencha no .env."
        )

    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.openai_api_key,
    )
