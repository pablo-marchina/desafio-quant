# rerank.py
import os
import sys
import cohere
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from pipeline.utils.rate_limiter import cohere_wait

load_dotenv()  # le o arquivo .env e carrega as variáveis

co = cohere.Client(os.environ["COHERE_API_KEY"])  # tier gratuito cobre bem o uso de um projeto de curso

def rerank(query: str, candidatos: list, top_n: int = 5):
    textos = [c["text"] for c in candidatos]
    cohere_wait()
    resposta = co.rerank(
        model="rerank-multilingual-v3.0",
        query=query,
        documents=textos,
        top_n=top_n
    )

    resultados_ordenados = []
    for r in resposta.results:
        item = candidatos[r.index]
        item["relevance_score"] = r.relevance_score
        resultados_ordenados.append(item)

    return resultados_ordenados