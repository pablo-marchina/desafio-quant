"""Script de exemplo — roda a cauda do pipeline e imprime os briefings.

Demonstra o NVISION da parte que mais ENSINA (RAG NVIDIA + recomendação +
briefing) SEM depender do scraper, que precisa de sites no ar e é instável.
Para isso, parte de perfis de startup já estruturados e VALIDADOS (como se o
extractor/classifier/evidence_validator já tivessem rodado) e executa só os
três últimos nós do grafo:

    rag_node -> recommendation_node -> briefing_node

Pré-requisitos (o resto do pipeline real exigiria também rede + scraping):
  - Qdrant indexado:  docker compose up -d qdrant  &&  uv run python -m rag.index
  - .env com OPENAI_API_KEY (embeddings) e COHERE_API_KEY (rerank)

Uso:
    uv run python scripts/run_pipeline.py
"""
import sys
from pathlib import Path

# Permite rodar como `python scripts/run_pipeline.py` a partir da raiz do repo,
# garantindo que os pacotes (agents, rag, core) sejam importáveis.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.briefing import briefing_node  # noqa: E402
from agents.fit_score import fit_score_node  # noqa: E402
from agents.rag import rag_node  # noqa: E402
from agents.recommendation import recommendation_node  # noqa: E402


def _validated(name, label, description, sector, ai_signals, tech_stack,
               confidence="high", stage=None, funding=None):
    """Monta um ValidatedStartup serializado (a forma que o rag_node espera)."""
    return {
        "classified": {
            "startup": {
                "name": name, "description": description, "sector": sector,
                "stage": stage, "funding": funding, "tech_stack": tech_stack,
                "ai_signals": ai_signals, "extraction_basis": "content",
            },
            "label": label,
            "rationale": "perfil de exemplo (script de demonstração)",
            "confidence": confidence,
        },
        "validation_confidence": confidence,
        "issues": [],
    }


# Startups de exemplo, escolhidas para mostrar comportamentos diferentes:
#  - ChatJurix : AI-native com LLM -> bom fit (NeMo Guardrails / inferência)
#  - VisionAgro: AI-native de visão -> a base cobre mal -> baixa confiança
#  - LogiBox   : Non-AI -> recomendação rebaixada e sinalizada como especulativa
EXEMPLOS = [
    _validated(
        "ChatJurix", "AI-native",
        "assistente jurídico com LLM próprio que responde sobre processos e gera petições",
        "legaltech",
        ["LLM próprio fine-tunado em jurisprudência", "RAG sobre documentos jurídicos",
         "inferência de baixa latência"],
        ["Python", "LangChain"], stage="seed", funding="R$ 3M (pre-seed)",
    ),
    _validated(
        "VisionAgro", "AI-native",
        "plataforma de visão computacional que detecta pragas em lavouras por imagens de drones",
        "agtech",
        ["modelos próprios de deep learning para visão computacional", "inferência em tempo real"],
        ["PyTorch"], stage="seed",
    ),
    _validated(
        "LogiBox", "Non-AI",
        "marketplace de fretes que conecta transportadoras a embarcadores",
        "logtech", [], ["Ruby on Rails"], stage="série A", funding="R$ 15M",
    ),
]


def main() -> None:
    state = {"validated_startups": EXEMPLOS}
    # Executa a cauda do pipeline em sequência, encadeando o estado.
    state.update(rag_node(state))
    state.update(recommendation_node(state))
    state.update(fit_score_node(state))
    state.update(briefing_node(state))

    # Ranking de prioridade (o diferencial) antes dos briefings detalhados.
    print("RANKING DE FIT (Inception)\n")
    for s in state["fit_scores"]:
        print(f"  {s['score']:>3}/100  [{s['tier']:^5}]  {s['name']}  ({s['label']})")
    print("\n" + "=" * 72 + "\n")

    for briefing in state["briefings"]:
        print(briefing["markdown"])
        print("\n" + "=" * 72 + "\n")


if __name__ == "__main__":
    main()
