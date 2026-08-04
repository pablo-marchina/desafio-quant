from pipeline.graph.state import AgentState
from pipeline.agents.search_planner import run_search_planner
from pipeline.agents.scraper import run_scraper
from pipeline.agents.extractor import run_extractor
from pipeline.agents.email_finder import run_email_finder
from pipeline.agents.classifier import run_classifier
from pipeline.agents.evidence_validator import run_evidence_validator
from pipeline.agents.rag_agent import run_rag_agent
from pipeline.agents.recommendation_agent import run_recommendation_agent
from pipeline.agents.briefing_agent import run_briefing_agent


def node_search_planner(state: AgentState) -> dict:
    queries = run_search_planner(state["setor_alvo"])
    return {"queries_geradas": queries, "etapa_atual": "search_planner", "iteracao": state.get("iteracao", 0) + 1}


def node_scraper(state: AgentState) -> dict:
    resultados = run_scraper(state["setor_alvo"], state.get("queries_geradas", []))
    return {"startups_coletadas": resultados, "etapa_atual": "scraper"}


def node_extractor(state: AgentState) -> dict:
    startups = run_extractor(state.get("startups_coletadas", []))
    return {"startups_coletadas": startups, "etapa_atual": "extractor"}


def node_email_finder(state: AgentState) -> dict:
    return run_email_finder(state.get("startups_coletadas", []))


def node_classifier(state: AgentState) -> dict:
    classificadas = run_classifier(
        state.get("startups_coletadas", []),
        setor_relevance=0.5
    )
    return {"startups_classificadas": classificadas, "etapa_atual": "classifier"}


def node_evidence_validator(state: AgentState) -> dict:
    validadas = run_evidence_validator(state.get("startups_classificadas", []))
    return {"startups_validadas": validadas, "etapa_atual": "evidence_validator"}


def node_rag_agent(state: AgentState) -> dict:
    recomendacoes = run_rag_agent(state.get("startups_validadas", []))
    return {"recomendacoes_rag": recomendacoes, "etapa_atual": "rag_agent"}


def node_recommendation_agent(state: AgentState) -> dict:
    finais = run_recommendation_agent(state.get("recomendacoes_rag", []))
    return {"recomendacoes_finais": finais, "etapa_atual": "recommendation_agent"}


def node_briefing_agent(state: AgentState) -> dict:
    briefings = run_briefing_agent(state.get("recomendacoes_finais", []))
    return {"briefings": briefings, "etapa_atual": "briefing_agent"}


def should_continue_after_scraping(state: AgentState) -> str:
    if len(state.get("startups_coletadas", [])) == 0:
        return "stop"
    return "continue"


def should_continue_after_validation(state: AgentState) -> str:
    validadas = state.get("startups_validadas", [])
    validas = [s for s in validadas if not s.get("low_confidence")]
    if len(validas) == 0:
        return "stop"
    return "continue"
