# busca_hibrida.py
import json
import os
import sys
import time
import cohere
from dotenv import load_dotenv
from rank_bm25 import BM25Okapi
from qdrant_client import QdrantClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from pipeline.utils.rate_limiter import cohere_wait

load_dotenv()

_SRC_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(_SRC_DIR, "chunks_with_embeddings.json"), "r", encoding="utf-8") as f:
    chunks = json.load(f)

co = cohere.Client(os.environ["COHERE_API_KEY"])

corpus_tokenizado = [c["text"].lower().split() for c in chunks]
bm25 = BM25Okapi(corpus_tokenizado)

client = QdrantClient(path=os.path.join(_SRC_DIR, "qdrant_local"))


def embed_com_retry(textos: list, tentativas: int = 3, espera_base: int = 5) -> list:
    for tentativa in range(1, tentativas + 1):
        try:
            cohere_wait()
            return co.embed(
                texts=textos,
                model="embed-multilingual-v3.0",
                input_type="search_query"
            ).embeddings
        except Exception as e:
            if tentativa == tentativas:
                raise
            espera = espera_base * (2 ** (tentativa - 1))
            print(f"[Cohere] erro na tentativa {tentativa}/{tentativas}: {e}. Tentando de novo em {espera}s...")
            time.sleep(espera)


def busca_hibrida(query: str, top_k: int = 10):
    query_vec = embed_com_retry([query])[0]

    # client.search() foi descontinuado nas versões recentes do qdrant-client;
    # o método atual é query_points(), que retorna os resultados em .points
    resultados_vetoriais = client.query_points(
        collection_name="nvidia_kb",
        query=query_vec,
        limit=top_k
    ).points

    # lexical
    scores_bm25 = bm25.get_scores(query.lower().split())
    top_bm25_idx = sorted(range(len(scores_bm25)), key=lambda i: scores_bm25[i], reverse=True)[:top_k]
    resultados_bm25 = [chunks[i] for i in top_bm25_idx]

    # combina e deduplica por id
    candidatos = {}
    for r in resultados_vetoriais:
        candidatos[r.id] = {"text": r.payload["text"], "url": r.payload["url"], "tech": r.payload["tech"]}
    for r in resultados_bm25:
        candidatos[r["id"]] = {"text": r["text"], "url": r["url"], "tech": r["tech"]}

    return list(candidatos.values())


if __name__ == "__main__":
    # roda só quando você executa "python busca_hibrida.py" diretamente,
    # não quando outro script importa a função
    resultados = busca_hibrida("latência de inferência em chatbot de atendimento")
    for r in resultados[:5]:
        print(r["tech"], "-", r["url"])