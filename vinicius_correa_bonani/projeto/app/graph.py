"""Grafo do pipeline: desvio condicional + loop.

Os 8 nós, com ramificação. O Evidence Validator vem ANTES do Classifier: ele faz o
grounding (limpa dados sem lastro) e é o ponto do loop de volta ao Search Planner
quando a evidência é insuficiente (teto em `tentativas`). Só então o Classifier
decide — sobre dados já verificados — e desvia `non-ai` direto para END (antes do
RAG, poupando a parte cara). Cada nó vive em seu arquivo; aqui só fazemos a fiação.

    START → search_planner → scraper → extractor → evidence_validator
      evidence_validator ──(insuf. e tentativas<teto)──→ search_planner   (loop)
      evidence_validator ──(ok ou teto)──→ classifier
      classifier ──(non-ai/sem-dados)──────────────────────────────────→ END
      classifier ──(ai-native/ai-enabled)──→ nvidia_rag → recommendation → briefing → END
"""

from langgraph.graph import END, START, StateGraph

from app.config import settings
from app.state import RadarState
from app.search_planner import search_planner
from app.scraper import scraper
from app.extractor import extractor
from app.classifier import classifier
from app.evidence_validator import evidence_validator
from app.nvidia_rag import nvidia_rag
from app.recommendation import recommendation
from app.briefing import briefing


def rota_classificacao(state: RadarState) -> str:
    """non-ai (ou sem dados coletados) encerra cedo; o resto segue para a validação."""
    return "fim" if state.classificacao in ("non-ai", "sem-dados") else "continua"


def rota_evidencia(state: RadarState) -> str:
    """Loop de volta ao Search Planner se a evidência for insuficiente e ainda
    houver tentativas; senão, segue para o RAG."""
    if not state.evidencias_ok and state.tentativas < settings.max_tentativas:
        return "coleta_mais"
    return "continua"


def build_graph():
    builder = StateGraph(RadarState)
    for name, fn in [
        ("search_planner", search_planner),
        ("scraper", scraper),
        ("extractor", extractor),
        ("classifier", classifier),
        ("evidence_validator", evidence_validator),
        ("nvidia_rag", nvidia_rag),
        ("recommendation", recommendation),
        ("briefing", briefing),
    ]:
        builder.add_node(name, fn)

    # trechos retos
    builder.add_edge(START, "search_planner")
    builder.add_edge("search_planner", "scraper")
    builder.add_edge("scraper", "extractor")
    builder.add_edge("extractor", "evidence_validator")
    builder.add_edge("nvidia_rag", "recommendation")
    builder.add_edge("recommendation", "briefing")
    builder.add_edge("briefing", END)

    # loop do Evidence Validator (com teto); ao sair, segue para o Classifier
    builder.add_conditional_edges(
        "evidence_validator",
        rota_evidencia,
        {"coleta_mais": "search_planner", "continua": "classifier"},
    )
    # desvio condicional após o Classifier (já sobre dados verificados)
    builder.add_conditional_edges(
        "classifier",
        rota_classificacao,
        {"fim": END, "continua": "nvidia_rag"},
    )
    return builder.compile()


graph = build_graph()


if __name__ == "__main__":
    final = graph.invoke(RadarState(consulta="Tractian"))
    classificacao = final.get("classificacao")
    score = final.get("score")
    print(f"[classificação: {classificacao}]")
    if score:
        print(f"[score composto: {score.composto}  "
              f"(ai-native {score.ai_native} · fit {score.nvidia_fit} · "
              f"tração {score.tracao} · time {score.time_ia})]")
    print()
    print(final.get("briefing") or "(encerrado cedo — non-ai)")
