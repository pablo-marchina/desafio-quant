# teste_validacao.py
from busca_hibrida import busca_hibrida
from rerank import rerank

queries_teste = [
    "startup que usa LLM em atendimento ao cliente via API externa",
    "processamento de grande volume de dados tabulares",
    "transcrição de voz e call center",
    "startup de saúde usando IA",
    "governança e controle de comportamento de agentes de IA",
]

for q in queries_teste:
    candidatos = busca_hibrida(q, top_k=10)
    resultados = rerank(q, candidatos, top_n=3)
    print(f"\nQuery: {q}")
    for r in resultados:
        print(f"  [{r['relevance_score']:.2f}] {r['tech']} - {r['url']}")