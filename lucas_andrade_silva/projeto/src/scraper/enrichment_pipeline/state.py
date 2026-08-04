"""Shared state for the startup enrichment graph."""

from __future__ import annotations

from typing import Any, TypedDict


class EnrichmentState(TypedDict, total=False):
    candidate: dict[str, Any]
    normalized_company_name: str
    source_candidates: list[dict[str, Any]]
    candidate_urls_queue: list[dict[str, Any]]
    candidate_attempts: list[dict[str, Any]]
    validated_sources: list[dict[str, Any]]
    rejected_sources: list[dict[str, Any]]
    validated_source: dict[str, Any]
    validated_url: str
    url_index: int
    identity_validation: dict[str, Any]
    identity_evidence: dict[str, Any]
    cnpj_data: dict[str, Any]
    raw_texts: dict[str, str]
    web_context: dict[str, str]
    evidence_urls: list[str]
    evidence_summary: str
    llm_summary: str
    github_profile: dict[str, Any]
    github_candidatos_testados: list[str]
    github_tentativas: int
    github_repo_validado: str | None
    github_validacao_status: str
    github_validacao_evidencia: str | None
    github_validacao_criterios: list[str]
    github_stack_evidence: list[dict[str, Any]]
    gupy_profile: dict[str, Any]
    tech_signals: dict[str, list[str]]
    ai_signals: list[str]
    open_jobs_signals: list[str]
    company_description: str
    enrichment_status: str
    identity_confidence_score: float
    tech_confidence_score: float
    final_status: str
    final_reason: str
    best_url: str
    discard_reason: str
    is_active: bool
    classification: dict[str, Any]
    errors: dict[str, list[str]] | list[str]
    dry_run: bool
    updated: bool
    save_skipped_reason: str
    log_summary: dict[str, Any]
    timings: dict[str, float]
    skipped_sources: list[str]
    run_identity_phase: bool
    run_deep_enrichment: bool
    skip_github: bool
    skip_gupy: bool
    skip_description: bool
    mode: str
