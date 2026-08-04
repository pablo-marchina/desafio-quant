"""Ingestão offline da base de conhecimento NVIDIA (roda UMA vez, fora do grafo).

    Documentos NVIDIA → scraping → chunking → embeddings → Qdrant

Uso: `python -m app.ingest`. Idempotente — recria a coleção a cada execução.
Requer a coleta funcionando (rede) e, com `embedding_provider=openai`, a chave OpenAI.
"""

from app import rag
from app.config import settings
from app.scraper import extract_text, fetch_url, permitido_por_robots
from app.sources import NVIDIA_DOCS


def main() -> None:
    print(f"Ingestão da base NVIDIA → coleção '{settings.qdrant_collection}' "
          f"(embeddings: {settings.embedding_provider})")
    rag.ensure_collection(recriar=True)

    todos: list[dict] = []
    for doc in NVIDIA_DOCS:
        url, titulo = doc["url"], doc.get("titulo", "")
        if not permitido_por_robots(url):
            print(f"  [robots bloqueou] {url}")
            continue
        html = fetch_url(url)
        if not html:
            print(f"  [falhou]         {titulo or url}")
            continue
        texto = rag.limpar(extract_text(html))   # corta changelog/emoji dos READMEs
        chunks = rag.chunk_texto(texto, fonte=url, titulo=titulo)
        todos.extend(chunks)
        print(f"  [ok] {titulo:<28} {len(chunks):>3} chunks  ({len(texto)} chars)")

    n = rag.indexar(todos)
    print(f"\nIngeridos {n} chunks de {len(NVIDIA_DOCS)} documentos.")


if __name__ == "__main__":
    main()
