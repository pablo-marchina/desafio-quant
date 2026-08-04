"""Testes de fumaça da fundação.

Validam que as peças centrais carregam e conversam, sem depender de chaves
de API nem de bancos no ar (o LLM é falso via `patch_get_llm`).
Rode com: `uv run pytest`
"""
from fastapi.testclient import TestClient

from agents.graph import graph
from agents.search_planner import SOURCE_CATALOG
from api.main import app

client = TestClient(app)


def test_health_ok():
    """O backend sobe e responde no /health."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_graph_runs_full_pipeline_to_briefing(
    patch_get_llm, patch_scraper_offline, fixed_search_plan
):
    """O grafo executa o pipeline completo: search_planner (LLM falso)
    -> scraper -> relevance -> enricher -> extractor -> classifier ->
    evidence_validator -> rag -> recommendation -> briefing.

    Roda OFFLINE: `patch_scraper_offline` faz toda fonte resolver "sem adapter",
    então o scraper não toca a rede; cada etapa seguinte recebe lista vazia e
    não toca o LLM. Sem startups, a cauda do pipeline não consulta serviço
    nenhum e encerra em END.
    """
    final = graph.invoke({"query": "fintechs de IA"})
    # search_planner_node usa os termos do LLM falso e varre TODAS as fontes
    assert final["search_terms"] == fixed_search_plan.search_terms
    assert final["sources"] == sorted(SOURCE_CATALOG)
    # scraper não encontrou adapter para essas fontes -> coleta vazia
    assert final["raw_startups"] == []
    # cada etapa subsequente recebe lista vazia e a propaga vazia
    assert final["extracted_startups"] == []
    assert final["classified_startups"] == []
    assert final["validated_startups"] == []
    # cauda do pipeline rodou sem startups -> vazios (e nada de rede)
    assert final["rag_contexts"] == []
    assert final["recommendations"] == []
    assert final["briefings"] == []
    # validator rodou uma vez; lista vazia -> seguiu pela cauda do pipeline e END
    assert final["validation_attempts"] == 1
    # messages (reducer add_messages): 1 planner + 1 por fonte (scraper, que agora
    # varre TODAS as fontes) + relevance + enricher + extractor + classifier
    # + evidence_validator + rag + recommendation + briefing
    assert len(final["messages"]) == 1 + len(final["sources"]) + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1


def test_demo_plan_endpoint(patch_get_llm, patch_scraper_offline, fixed_search_plan):
    """O endpoint de demo executa o grafo via HTTP, com LLM falso."""
    resp = client.post("/api/demo/plan", json={"query": "fintechs de IA"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["search_terms"] == fixed_search_plan.search_terms
    assert body["sources"] == sorted(SOURCE_CATALOG)
