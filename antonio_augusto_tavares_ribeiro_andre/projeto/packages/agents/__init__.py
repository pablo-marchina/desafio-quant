"""Grafo LangGraph e nós dos agentes (F2).

Nós: search_planner, scraper, extractor, classifier, evidence_validator,
nvidia_rag, recommender, gpu_benchmark, human_review (HITL/F2.8), briefing. Estado em
GraphState; backbone montado em `graph.py` (F2.1); checkpointer Postgres (F2.2).

Cliente Nemotron (F0.7), prompts versionados (F0.12) e a montagem do grafo (F2.1)
expostos aqui: `from packages.agents import get_chat, get_prompt, run_pipeline`.
"""

from .briefing import (
    build_briefing,
    make_briefing,
    parse_refinement,
    refine_with_llm,
    render_markdown,
    render_pdf,
)
from .cache import (
    DiskCache,
    LLMCache,
    MemoryCache,
    NullCache,
    RedisCache,
    cache_from_settings,
    cache_key,
    cached_completion,
)
from .checkpoint import postgres_checkpointer, run_pipeline_persisted, state_serde
from .classifier import (
    classify_with_llm,
    heuristic_score,
    is_confident_non_ai,
    make_aimi,
    parse_score,
)
from .cohort import (
    CohortCandidate,
    CohortOutcome,
    CohortReport,
    build_cohort,
    candidate_domains,
    candidates_from_seed,
    discover_candidates,
)
from .evidence_validator import (
    MIN_SOURCES,
    evidence_sources,
    is_sufficient,
)
from .extractor import extract_profile, parse_profile
from .graph import CONDITIONAL_OUT, PIPELINE, build_graph, compile_graph, run_pipeline
from .guardrails import (
    BlockedRecommendation,
    GuardrailReport,
    check_recommendations,
    evidence_violations,
    guard_recommendations,
)
from .human_review import review_payload
from .inception import inception_priority
from .llm import Profile, get_chat, reasoning_system_message, smoke
from .nodes import NODES
from .nvidia_rag import build_rag_queries, gap_pillars, get_kb_retriever, retrieve_evidence
from .progress import (
    ProgressEvent,
    RedisProgressPublisher,
    progress_channel,
    resume_pipeline,
    stream_pipeline,
    subscribe_progress,
)
from .prompts import PROMPT_NODES, Prompt, get_prompt
from .recommend_rules import (
    PILLAR_RULES,
    SECTOR_RULES,
    SectorRule,
    TechCandidate,
    TechRule,
    match_sector,
    match_techs,
    recommendable_kb_techs,
    techs_for_pillar,
)
from .recommender import (
    build_recommendations,
    gap_evidence_for,
    make_recommendations,
    nvidia_evidence_for,
    parse_refinements,
    recommend_with_llm,
)
from .search_planner import (
    PrioritizedSource,
    SearchPlan,
    detect_mode,
    deterministic_plan,
    make_plan,
    resolve_mode,
)
from .terminals import insufficient_data_briefing, out_of_scope_briefing

__all__ = [
    # LLM (F0.7)
    "get_chat",
    "reasoning_system_message",
    "smoke",
    "Profile",
    # prompts (F0.12)
    "get_prompt",
    "Prompt",
    "PROMPT_NODES",
    # grafo (F2.1)
    "build_graph",
    "compile_graph",
    "run_pipeline",
    # cohort builder — sourcing em lote (F1.14)
    "CohortCandidate",
    "CohortOutcome",
    "CohortReport",
    "build_cohort",
    "candidate_domains",
    "candidates_from_seed",
    "discover_candidates",
    "PIPELINE",
    "CONDITIONAL_OUT",
    "NODES",
    # search_planner (F2.3)
    "SearchPlan",
    "PrioritizedSource",
    "make_plan",
    "deterministic_plan",
    "detect_mode",
    "resolve_mode",
    # extractor (F2.5) — o nó é acessado via NODES (evita shadowing do submódulo)
    "extract_profile",
    "parse_profile",
    # classifier (F2.6) — o nó é acessado via NODES (evita shadowing do submódulo)
    "heuristic_score",
    "parse_score",
    "classify_with_llm",
    "make_aimi",
    "is_confident_non_ai",
    # Inception Priority — fila de outreach 0–100 derivada do AIMI (F6.13)
    "inception_priority",
    # evidence_validator (F2.7) — o nó é acessado via NODES (evita shadowing do submódulo)
    "evidence_sources",
    "is_sufficient",
    "MIN_SOURCES",
    # nvidia_rag (F3.7) — o nó é acessado via NODES (evita shadowing do submódulo)
    "build_rag_queries",
    "gap_pillars",
    "retrieve_evidence",
    "get_kb_retriever",
    # mapa de regras gap → tech NVIDIA (F4.1) — base determinística do recommender (F4.2)
    "TechRule",
    "SectorRule",
    "TechCandidate",
    "PILLAR_RULES",
    "SECTOR_RULES",
    "techs_for_pillar",
    "match_sector",
    "match_techs",
    "recommendable_kb_techs",
    # recommender (F4.2/F4.3) — o nó é acessado via NODES (evita shadowing do submódulo)
    "build_recommendations",
    "nvidia_evidence_for",
    "gap_evidence_for",
    "make_recommendations",
    "recommend_with_llm",
    "parse_refinements",
    # briefing executivo normal (F4.4) — o nó é acessado via NODES (evita shadowing do submódulo)
    "build_briefing",
    "make_briefing",
    "render_markdown",
    "render_pdf",
    "parse_refinement",
    "refine_with_llm",
    # NeMo Guardrails — rail de evidência do briefing (F4.5)
    "evidence_violations",
    "check_recommendations",
    "guard_recommendations",
    "GuardrailReport",
    "BlockedRecommendation",
    # terminais de baixa confiança / fora de escopo (F2.12 / F2.13)
    "insufficient_data_briefing",
    "out_of_scope_briefing",
    # human_review (F2.8) — o nó é acessado via NODES (evita shadowing do submódulo)
    "review_payload",
    # progresso ao vivo + worker async (F2.10)
    "stream_pipeline",
    "resume_pipeline",
    "ProgressEvent",
    "progress_channel",
    "RedisProgressPublisher",
    "subscribe_progress",
    # cache de inferência LLM por prompt+modelo+versão (F2.14)
    "cached_completion",
    "cache_key",
    "cache_from_settings",
    "LLMCache",
    "NullCache",
    "MemoryCache",
    "DiskCache",
    "RedisCache",
    # checkpointer Postgres (F2.2)
    "postgres_checkpointer",
    "run_pipeline_persisted",
    "state_serde",
]
