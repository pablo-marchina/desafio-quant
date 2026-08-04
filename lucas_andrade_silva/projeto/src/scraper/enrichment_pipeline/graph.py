"""LangGraph assembly for the enrichment pipeline."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from .nodes.ai_classification import ai_classification_node
from .nodes.build_summary import build_summary_node
from .nodes.candidate_url_loop import candidate_url_loop_node
from .nodes.cnpj_lookup import cnpj_lookup_node
from .nodes.description_generation import description_generation_node
from .nodes.github_lookup import github_lookup_node
from .nodes.gupy_lookup import gupy_lookup_node
from .nodes.log_result import log_result_node
from .nodes.normalize_company import normalize_company_name_node
from .nodes.source_discovery import source_discovery_node
from .nodes.tech_signal_detection import tech_signal_detection_node
from .nodes.update_supabase import update_supabase_node
from .nodes.validation_gate import validation_gate_node
from .nodes.web_context_lookup import web_context_lookup_node
from .state import EnrichmentState


def build_enrichment_graph():
    builder = StateGraph(EnrichmentState)
    builder.add_node("normalize_company_name", normalize_company_name_node)
    builder.add_node("source_discovery", source_discovery_node)
    builder.add_node("candidate_url_loop", candidate_url_loop_node)
    builder.add_node("cnpj_lookup", cnpj_lookup_node)
    builder.add_node("github_lookup", github_lookup_node)
    builder.add_node("gupy_lookup", gupy_lookup_node)
    builder.add_node("web_context_lookup", web_context_lookup_node)
    builder.add_node("build_summary", build_summary_node)
    builder.add_node("tech_signal_detection", tech_signal_detection_node)
    builder.add_node("ai_classification", ai_classification_node)
    builder.add_node("description_generation", description_generation_node)
    builder.add_node("validation_gate", validation_gate_node)
    builder.add_node("update_supabase", update_supabase_node)
    builder.add_node("log_result", log_result_node)

    builder.add_edge(START, "normalize_company_name")
    builder.add_edge("normalize_company_name", "source_discovery")
    builder.add_edge("source_discovery", "candidate_url_loop")
    builder.add_edge("candidate_url_loop", "cnpj_lookup")
    builder.add_edge("cnpj_lookup", "github_lookup")
    builder.add_edge("github_lookup", "gupy_lookup")
    builder.add_edge("gupy_lookup", "web_context_lookup")
    builder.add_edge("web_context_lookup", "build_summary")
    builder.add_edge("build_summary", "tech_signal_detection")
    builder.add_edge("tech_signal_detection", "ai_classification")
    builder.add_edge("ai_classification", "description_generation")
    builder.add_edge("description_generation", "validation_gate")
    builder.add_edge("validation_gate", "update_supabase")
    builder.add_edge("update_supabase", "log_result")
    builder.add_edge("log_result", END)
    return builder.compile()


enrichment_graph = build_enrichment_graph()
