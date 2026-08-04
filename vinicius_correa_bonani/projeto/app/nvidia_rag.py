"""NVIDIA RAG — lado online da recuperação.

Monta uma query a partir do perfil da empresa e recupera o contexto técnico da
base NVIDIA (Qdrant) via busca híbrida + Cohere Rerank. Preenche `contexto_rag`
com trechos citados (cada um com sua fonte) — assim a Recommendation
não inventa specs. A ingestão offline (app/ingest.py) precisa ter rodado antes.
"""

from app import rag
from app.state import RadarState


def _montar_query(state: RadarState) -> str:
    # Lidera pelas NECESSIDADES técnicas (casa com Triton/TensorRT-LLM/RAPIDS/etc.);
    # os sinais da empresa entram só como contexto. Evita o viés de marketing do
    # Inception que a frase "empresa de IA" provocava.
    base = (
        "inferência de modelos, serving em produção, otimização de latência, "
        "treinamento e customização de modelos, processamento de dados em GPU"
    )
    d = state.dados_estruturados
    if not d:
        return base
    sinais = " ".join(filter(None, [d.setor, " ".join(d.tecnologias)]))
    return f"Tecnologias NVIDIA para: {base}. Contexto técnico da empresa: {sinais}"


def nvidia_rag(state: RadarState) -> dict:
    query = _montar_query(state)
    passagens = rag.recuperar(query)
    contexto = [f"{p['texto']} [fonte: {p['fonte']}]" for p in passagens]
    return {"contexto_rag": contexto}
