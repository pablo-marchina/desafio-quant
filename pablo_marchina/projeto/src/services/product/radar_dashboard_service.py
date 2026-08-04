from __future__ import annotations

"""Central runtime service for the company recommendation dashboard.

This service intentionally does not contain mock companies, static rankings, or
pre-filled recommendations. It consolidates the active runtime path:

discovery sources -> candidate promotion -> LangGraph workflow -> activation
recommendations -> opportunity scoring -> dossier -> dashboard rows.
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from src.database.models import AnalysisRun, Startup
from src.discovery.source_registry import load_sources
from src.discovery.service import StartupDiscoveryService
from src.discovery.candidate_quality import evaluate_candidate_quality, is_blocked_website, is_directory_or_aggregator_url
from src.repositories.product import ProductRepository
from src.scraping.scrapers import scraper_registry  # imports scraper modules and populates registry
from src.services.product.activation_service import ActivationPlaybookService
from src.services.product.dossier_service import ActivationDossierService
from src.services.product.opportunity_score_service import OpportunityScoreService
from src.services.product.opportunity_service import OpportunityService


_CONFIDENCE_VALUE = {"high": 0.90, "medium": 0.60, "low": 0.30, "unknown": 0.0}
_TERMINAL_RUN_STATUSES = {"completed", "degraded", "awaiting_review"}
_VALID_SOURCE_TYPES = {"official_site", "news", "directory", "blog", "job_post", "founder_profile"}
_SOURCE_TYPE_ALIASES = {"web": "directory", "manual_seed": "directory", "official_website": "official_site", "website": "official_site", "social": "founder_profile"}


@dataclass(frozen=True)
class PopulateOptions:
    limit: int = 100
    source_limit: int = 6
    pipeline_limit: int = 5
    run_pipeline: bool = True
    force_rerun: bool = False


class RadarDashboardService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.product_repo = ProductRepository(session)
        self.discovery = StartupDiscoveryService(session)

    def populate(self, options: PopulateOptions) -> dict[str, Any]:
        """Populate the dashboard through the single runtime pipeline.

        The method is adaptive: available sources, source scraper registry,
        already-persisted candidates, current readiness, and latest run status
        determine what is executed. It never falls back to fixture companies.
        """

        discovery_results = []
        seed_result = self._run_verified_seed_discovery()
        if seed_result is not None:
            discovery_results.append(seed_result)
        discovery_results.extend(self._run_available_source_scrapers(options.source_limit))
        self._mark_invalid_runtime_entities()
        pipeline_limit = max(0, min(int(options.pipeline_limit), 25))
        promoted = self._promote_best_candidates(pipeline_limit if options.run_pipeline else 0)
        pipeline_results: list[dict[str, Any]] = []

        if options.run_pipeline and pipeline_limit > 0:
            startup_ids = self._startup_ids_for_runtime(limit=pipeline_limit, promoted=promoted)
            pipeline_results = self._run_pipeline_for_startups(
                startup_ids,
                force_rerun=options.force_rerun,
            )

        dashboard = self.dashboard(limit=options.limit)
        return {
            "status": "completed",
            "message": "Dashboard populated from active runtime sources only.",
            "discovery_results": discovery_results,
            "promoted_candidates": promoted,
            "pipeline_results": pipeline_results,
            "dashboard": dashboard,
            "discovery_queue": self._discovery_queue(limit=100),
            "rejected_entities": self._rejected_entities(limit=100),
        }

    def dashboard(self, *, limit: int = 100) -> dict[str, Any]:
        """Return a consolidated dashboard with analyzed startups first."""

        opportunity_service = OpportunityService(self.session)
        opportunity_items, opportunity_total = opportunity_service.list_opportunities(limit=limit)
        rows: list[dict[str, Any]] = []
        seen_startup_ids: set[str] = set()

        for item in opportunity_items:
            startup_id = str(item.get("startup_id") or "")
            run_id = item.get("latest_analysis_run_id")
            run = self.product_repo.get_analysis_run(str(run_id)) if run_id else None
            if run is None or run.startup is None or not self._is_valid_startup_entity(run.startup):
                continue
            row = self._opportunity_row(item, run)
            seen_startup_ids.add(startup_id)
            rows.append(row)

        # Non-analyzed startups are intentionally hidden from the dashboard.
        # They remain accessible in discovery/startup management views.

        # The dashboard is an execution result, not a discovery inbox.
        # Unpromoted candidates stay out of this table until they become valid,
        # analyzed startups with runtime artifacts. This prevents menu labels,
        # directories, events, and social profiles from appearing as companies.

        rows.sort(key=self._dashboard_sort_key, reverse=True)
        return {
            "items": rows[:limit],
            "total": len(rows[:limit]),
            "analyzed_total": opportunity_total,
            "limit": limit,
        }

    def _run_verified_seed_discovery(self) -> dict[str, Any] | None:
        """Load source-backed seed companies as governed research inputs.

        The seed file is not a mock dataset: every entry must carry a public
        evidence URL and an AI-specific evidence excerpt. Runtime quality gates
        still reject entries with generic names, social/navigation URLs, or no
        entity-level AI signal.
        """
        import json
        from pathlib import Path

        path = Path(__file__).resolve().parents[3] / "data" / "verified_brazilian_ai_startups.json"
        if not path.exists():
            return None
        entries = json.loads(path.read_text(encoding="utf-8"))
        result = self.discovery.run_manual_seed_discovery(
            entries,
            source_id="verified_public_research_seed_br_ai_startups",
        )
        return {"source_id": "verified_public_research_seed_br_ai_startups", "status": result.get("status"), **result}

    def _run_available_source_scrapers(self, source_limit: int) -> list[dict[str, Any]]:
        sources = load_sources()
        runnable_source_ids = [
            source_id
            for source_id, source in sources.items()
            if source.enabled_by_default and source.is_usable() and source_id in scraper_registry
        ]
        # Adaptive priority: higher allowed request rates first, then stable ids for reproducibility.
        runnable_source_ids.sort(key=lambda sid: (sources[sid].rate_limit_hint, sid), reverse=True)
        results: list[dict[str, Any]] = []
        for source_id in runnable_source_ids[: max(source_limit, 0)]:
            try:
                result = self.discovery.run_source_scraper_discovery(source_id)
                results.append({"source_id": source_id, "status": "completed", **result})
            except Exception as exc:  # optional external acquisition must not block the central pipeline
                error = str(exc)
                status = "unavailable" if error.startswith("fetch_failed:") else "failed"
                results.append(
                    {
                        "source_id": source_id,
                        "status": status,
                        "error": error,
                        "blocking": status == "failed",
                    }
                )
        return results

    def _promote_best_candidates(self, limit: int) -> list[dict[str, Any]]:
        candidates = self.discovery.list_candidates(limit=max(limit * 5, limit), status="new")
        candidates = [candidate for candidate in candidates if self._is_valid_candidate_entity(candidate)]
        candidates = sorted(candidates, key=self._candidate_priority, reverse=True)
        promoted: list[dict[str, Any]] = []
        for candidate in candidates[:limit]:
            try:
                result = self.discovery.promote_candidate(candidate.id)
                promoted.append(result)
            except Exception as exc:
                promoted.append({"candidate_id": candidate.id, "status": "failed", "error": str(exc)})
        return promoted

    def _startup_ids_for_runtime(self, *, limit: int, promoted: list[dict[str, Any]]) -> list[str]:
        ids: list[str] = []
        for item in promoted:
            startup_id = item.get("startup_id")
            if startup_id and startup_id not in ids:
                ids.append(str(startup_id))
        for startup in self.product_repo.list_startups(limit=limit * 3):
            if not self._is_valid_startup_entity(startup):
                continue
            if startup.id not in ids:
                ids.append(startup.id)
            if len(ids) >= limit:
                break
        return ids[:limit]

    def _run_pipeline_for_startups(self, startup_ids: list[str], *, force_rerun: bool) -> list[dict[str, Any]]:
        from src.repositories.workflow import WorkflowRepository
        from src.services.product.service import ProductService

        results: list[dict[str, Any]] = []
        product_service = ProductService(self.session)
        workflow_repo = WorkflowRepository(self.session)
        for startup_id in startup_ids:
            latest = self.product_repo.get_latest_analysis_run(startup_id)
            if latest is not None and latest.status in _TERMINAL_RUN_STATUSES and not force_rerun:
                run = latest
            else:
                try:
                    run = product_service.create_analysis_run_for_startup(
                        startup_id,
                        use_rag=True,
                        rag_backend="qdrant",
                        pipeline_version="radar_dashboard_unified_runtime_v2",
                    )
                except Exception as exc:
                    self.session.rollback()
                    results.append(
                        {
                            "startup_id": startup_id,
                            "status": "failed",
                            "error": f"{type(exc).__name__}: {exc}",
                            "blocking": True,
                        }
                    )
                    continue

            analysis_run_id = run.id
            status = str(run.status)
            workflow = workflow_repo.get_workflow_for_analysis_run(analysis_run_id)
            workflow_id = workflow.id if workflow is not None else None
            artifact_errors: list[str] = []
            if status in {"completed", "degraded"}:
                artifact_errors = self._ensure_post_pipeline_artifacts(analysis_run_id)

            result_status = "degraded" if artifact_errors and status == "completed" else status
            error = str(run.error_message or (workflow.error_message if workflow is not None else "") or "")
            degraded_reason = str(
                run.degraded_reason or (workflow.degraded_reason if workflow is not None else "") or ""
            )
            results.append(
                {
                    "startup_id": startup_id,
                    "analysis_run_id": analysis_run_id,
                    "workflow_id": workflow_id,
                    "status": result_status,
                    "current_node": workflow.current_node if workflow is not None else "",
                    "error": error or None,
                    "degraded_reason": degraded_reason or None,
                    "artifact_errors": artifact_errors,
                    "blocking": result_status == "failed",
                }
            )
        return results

    def _ensure_post_pipeline_artifacts(self, analysis_run_id: str) -> list[str]:
        # These are idempotent/replacing operations and keep all dashboard columns fed by runtime artifacts.
        errors: list[str] = []
        operations = (
            ("activation_recommendations", lambda: ActivationPlaybookService(self.session).persist_recommendations_for_run(analysis_run_id)),
            ("activation_dossier", lambda: ActivationDossierService(self.session).build_dossier_for_analysis_run(analysis_run_id)),
            ("opportunity_score", lambda: OpportunityScoreService(self.session).compute_score(analysis_run_id)),
        )
        for artifact_name, operation in operations:
            try:
                operation()
            except Exception as exc:
                self.session.rollback()
                errors.append(f"{artifact_name}: {type(exc).__name__}: {exc}")
        return errors

    def _mark_invalid_runtime_entities(self) -> None:
        changed = False
        for candidate in self.discovery.list_candidates(limit=10000, status="new"):
            if not self._is_valid_candidate_entity(candidate):
                candidate.status = "rejected_invalid_entity"
                meta = dict(candidate.metadata_json or {})
                meta["runtime_rejection_reason"] = "candidate_quality_gate_failed"
                candidate.metadata_json = meta
                changed = True
        for startup in self.product_repo.list_startups(limit=10000):
            for evidence in startup.evidence or []:
                normalized_source_type = _SOURCE_TYPE_ALIASES.get(
                    str(evidence.source_type or "").strip().casefold(),
                    str(evidence.source_type or "").strip().casefold(),
                )
                if normalized_source_type not in _VALID_SOURCE_TYPES:
                    normalized_source_type = "directory"
                if evidence.source_type != normalized_source_type:
                    evidence.source_type = normalized_source_type
                    changed = True
            if not self._is_valid_startup_entity(startup):
                startup.status = "rejected_invalid_entity"
                changed = True
        if changed:
            self.session.commit()

    @staticmethod
    def _is_valid_candidate_entity(candidate: Any) -> bool:
        signals = candidate.ai_native_signals_json or {}
        quality = evaluate_candidate_quality(
            name=str(candidate.discovered_name or ""),
            website=str(candidate.website or candidate.source_url or ""),
            description=str(candidate.description or candidate.raw_text_excerpt or ""),
            source_id=str(candidate.source_id or ""),
            signal_count=int(signals.get("signal_count") or 0),
            evidence_count=len(candidate.evidence_refs_json or []),
        )
        return quality.accepted

    @staticmethod
    def _is_valid_startup_entity(startup: Startup) -> bool:
        if getattr(startup, "status", "") == "rejected_invalid_entity":
            return False
        if is_blocked_website(startup.website) or is_directory_or_aggregator_url(startup.website):
            return False
        signal_count = 0
        for ev in startup.evidence or []:
            text = f"{ev.claim} {ev.quote_or_evidence}".casefold()
            if any(term in text for term in ("ai", "ia", "inteligência artificial", "machine learning", "llm", "deep learning")):
                signal_count += 1
        quality = evaluate_candidate_quality(
            name=startup.name,
            website=startup.website,
            description=f"{startup.description} {startup.product_summary}",
            source_id="persisted_startup",
            signal_count=signal_count,
            evidence_count=len(startup.evidence or []),
        )
        return quality.accepted

    @staticmethod
    def _candidate_priority(candidate: Any) -> float:
        signals = candidate.ai_native_signals_json or {}
        signal_count = float(signals.get("signal_count") or 0.0)
        has_website = 1.0 if candidate.website else 0.0
        evidence_count = float(len(candidate.evidence_refs_json or []))
        return (
            _CONFIDENCE_VALUE.get(candidate.confidence, 0.0)
            + min(signal_count / 10.0, 0.5)
            + min(evidence_count / 20.0, 0.25)
            + 0.15 * has_website
        )

    @staticmethod
    def _rank_technologies_for_startup(technologies: list[str], run: AnalysisRun | None) -> list[dict[str, Any]]:
        if run is None or run.startup is None:
            return []
        from src.services.product.workload_classifier import (
            classify_workloads,
            needs_guardrails,
            recommended_technologies,
        )

        startup = run.startup
        evidence_text = " ".join(
            f"{evidence.claim} {evidence.quote_or_evidence}"
            for evidence in (startup.evidence or [])
        )
        profile = (run.output_snapshot_json or {}).get("startup_profile") or {}
        text = " ".join(
            [
                str(startup.description or ""),
                str(startup.product_summary or ""),
                str(profile.get("description") or ""),
                " ".join(str(value) for value in profile.get("ai_signals", []) or []),
                " ".join(str(value) for value in profile.get("tech_stack_signals", []) or []),
                evidence_text,
            ]
        )
        matches = classify_workloads(text, max_families=2)
        if not matches:
            return []

        ordered = recommended_technologies(matches, limit=6)
        if needs_guardrails(text) and any(match.family == "llm_nlp" for match in matches):
            ordered.insert(min(2, len(ordered)), "NeMo Guardrails")
        ordered = list(dict.fromkeys(ordered))[:5]

        aliases = {
            "NVIDIA TensorRT": "TensorRT",
            "NVIDIA RAPIDS": "RAPIDS",
            "RAPIDS cuDF": "cuDF",
            "RAPIDS cuML": "cuML",
            "Clara / MONAI": "MONAI",
        }
        available = {aliases.get(str(value), str(value)) for value in technologies if value}
        ranked: list[dict[str, Any]] = []
        for index, technology in enumerate(ordered):
            # Profile-backed recommendations may be generated after mapping, so
            # keep evidence-backed technologies even when no mapping record has
            # been persisted yet. Existing mappings receive a small boost.
            score = 1.0 - (index * 0.08) + (0.08 if technology in available else 0.0)
            ranked.append(
                {
                    "technology": technology,
                    "runtime_fit_score": round(max(0.0, score), 4),
                    "workload_families": [match.family for match in matches if technology in match.technologies],
                    "matched_phrases": [
                        phrase
                        for match in matches
                        if technology in match.technologies
                        for phrase in match.matched_phrases[:4]
                    ],
                }
            )
        return ranked

    def _discovery_queue(self, *, limit: int = 100) -> list[dict[str, Any]]:
        rows = []
        for candidate in self.discovery.list_candidates(limit=limit, status="new"):
            rows.append({
                "candidate_id": candidate.id,
                "company_name": candidate.discovered_name,
                "website": candidate.website,
                "sector": candidate.sector,
                "status": candidate.status,
                "confidence": candidate.confidence,
                "source_id": candidate.source_id,
                "quality_score": (candidate.metadata_json or {}).get("candidate_quality_score"),
            })
        return rows

    def _rejected_entities(self, *, limit: int = 100) -> list[dict[str, Any]]:
        rows = []
        for candidate in self.discovery.list_candidates(limit=limit, status="rejected_invalid_entity"):
            rows.append({
                "candidate_id": candidate.id,
                "company_name": candidate.discovered_name,
                "website": candidate.website,
                "sector": candidate.sector,
                "status": candidate.status,
                "source_id": candidate.source_id,
                "rejection_reason": (candidate.metadata_json or {}).get("runtime_rejection_reason"),
                "quality_features": (candidate.metadata_json or {}).get("candidate_quality_features"),
            })
        return rows

    def _opportunity_row(self, item: dict[str, Any], run: AnalysisRun | None) -> dict[str, Any]:
        recommendations = []
        top_technologies: list[str] = []
        if run is not None:
            for rec in ActivationPlaybookService(self.session).get_recommendations_for_run(run.id):
                techs = [str(t) for t in rec.get("nvidia_technologies", [])]
                top_technologies.extend(techs)
                recommendations.append(
                    {
                        "playbook_name": rec.get("playbook_name"),
                        "priority": rec.get("priority"),
                        "confidence": rec.get("confidence"),
                        "nvidia_technologies": techs,
                        "recommended_motion": rec.get("recommended_motion"),
                        "next_step": rec.get("next_step"),
                        "reasoning": rec.get("reasoning"),
                        "success_metrics": rec.get("success_metrics", []),
                    }
                )
        startup = run.startup if run is not None else None
        ranked_technologies = self._rank_technologies_for_startup(top_technologies or item.get("top_nvidia_mappings", []), run)
        return {
            "row_type": "analyzed_startup",
            "startup_id": item.get("startup_id"),
            "candidate_id": None,
            "company_name": item.get("startup_name"),
            "website": getattr(run.startup, "website", "") if run and run.startup else "",
            "sector": getattr(run.startup, "sector", "") if run and run.startup else "",
            "country": getattr(run.startup, "country", "Brazil") if run and run.startup else "Brazil",
            "analysis_run_id": item.get("latest_analysis_run_id"),
            "analysis_status": getattr(run, "status", None),
            "recommendation_status": "ready" if recommendations else "missing_recommendations",
            "recommended_motion": item.get("recommended_motion"),
            "opportunity_score": item.get("composite_score"),
            "score_tier": item.get("confidence"),
            "confidence": item.get("confidence"),
            "evidence_coverage": item.get("evidence_coverage"),
            "unsupported_claim_count": item.get("unsupported_claim_count"),
            "top_gaps": self._relevant_top_gaps(run),
            "top_nvidia_technologies": [item["technology"] for item in ranked_technologies],
            "activation_recommendations": recommendations,
            "source_count": self._source_count(run),
            "information": {
                "description": getattr(startup, "description", "") if startup is not None else "",
                "product_summary": getattr(startup, "product_summary", "") if startup is not None else "",
                "tags": getattr(startup, "tags_json", []) if startup is not None else [],
                "evidence_sources": self._evidence_sources(run),
                "technology_ranking": ranked_technologies,
                "scores": self._scores(run),
                "gaps": self._gaps(run),
                "mappings": self._mappings(run),
                "dossier_available": item.get("dossier_available"),
                "export_readiness_score": item.get("export_readiness_score"),
                "review_readiness_score": item.get("review_readiness_score"),
            },
        }

    @staticmethod
    def _relevant_top_gaps(run: AnalysisRun | None) -> list[str]:
        """Expose only evidence-supported, medium/high-confidence runtime gaps."""
        if run is None or run.startup is None:
            return []

        from src.services.product.workload_classifier import classify_workloads, needs_guardrails

        startup = run.startup
        evidence_text = " ".join(
            f"{evidence.claim} {evidence.quote_or_evidence}"
            for evidence in (startup.evidence or [])
        )
        profile = (run.output_snapshot_json or {}).get("startup_profile") or {}
        text = " ".join(
            [
                str(startup.description or ""),
                str(startup.product_summary or ""),
                str(profile.get("description") or ""),
                " ".join(str(value) for value in profile.get("ai_signals", []) or []),
                " ".join(str(value) for value in profile.get("tech_stack_signals", []) or []),
                evidence_text,
            ]
        )
        matches = classify_workloads(text, max_families=2)
        if not matches:
            return []

        family_gaps = {
            "llm_nlp": {
                "agent_governance_gap",
                "model_evaluation_gap",
                "observability_gap",
                "high_latency",
                "high_inference_cost",
                "external_api_dependency",
            },
            "voice": {"voice_need", "high_latency", "observability_gap"},
            "computer_vision": {"computer_vision_need", "high_latency", "observability_gap"},
            "tabular_ml": {
                "heavy_tabular_processing",
                "slow_data_pipeline",
                "high_training_cost",
                "high_inference_cost",
            },
            "robotics_simulation": {"robotics_need", "simulation_need"},
            "cybersecurity": {"ai_cybersecurity_need"},
            "medical_imaging": {"healthcare_compliance_need", "computer_vision_need"},
        }
        allowed: set[str] = set()
        for match in matches:
            allowed.update(family_gaps.get(match.family, set()))
        if needs_guardrails(text) and any(match.family == "llm_nlp" for match in matches):
            allowed.add("agent_governance_gap")

        confidence_rank = {"high": 2, "medium": 1}
        supported = [
            gap
            for gap in run.gaps
            if gap.detected
            and gap.gap_type in allowed
            and str(gap.confidence or "").casefold() in confidence_rank
        ]
        supported.sort(
            key=lambda gap: (
                confidence_rank.get(str(gap.confidence or "").casefold(), 0),
                gap.gap_type,
            ),
            reverse=True,
        )
        return [gap.gap_type for gap in supported[:3]]

    def _startup_row(self, startup: Startup, latest: AnalysisRun | None) -> dict[str, Any]:
        return {
            "row_type": "startup_without_completed_analysis",
            "startup_id": startup.id,
            "candidate_id": None,
            "company_name": startup.name,
            "website": startup.website,
            "sector": startup.sector,
            "country": startup.country,
            "analysis_run_id": latest.id if latest else None,
            "analysis_status": latest.status if latest else "not_analyzed",
            "recommendation_status": "not_ready",
            "recommended_motion": None,
            "opportunity_score": None,
            "score_tier": None,
            "confidence": None,
            "evidence_coverage": None,
            "unsupported_claim_count": None,
            "top_gaps": [],
            "top_nvidia_technologies": [],
            "activation_recommendations": [],
            "source_count": len(startup.evidence or []),
            "information": {
                "description": startup.description,
                "product_summary": startup.product_summary,
                "tags": startup.tags_json,
            },
        }

    @staticmethod
    def _scores(run: AnalysisRun | None) -> dict[str, Any]:
        if run is None:
            return {}
        return {score.score_type: {"value": score.value, "confidence": score.confidence, "components": score.components_json} for score in run.scores}

    @staticmethod
    def _gaps(run: AnalysisRun | None) -> list[dict[str, Any]]:
        if run is None:
            return []
        return [
            {
                "gap_type": gap.gap_type,
                "detected": gap.detected,
                "confidence": gap.confidence,
                "reasoning": gap.reasoning,
                "evidence_refs": gap.evidence_refs_json,
            }
            for gap in run.gaps
        ]

    @staticmethod
    def _mappings(run: AnalysisRun | None) -> list[dict[str, Any]]:
        if run is None:
            return []
        return [
            {
                "technology_name": mapping.technology_name,
                "addresses_gap": mapping.addresses_gap,
                "priority": mapping.priority,
                "justification": mapping.justification,
                "recommendation_action": mapping.recommendation_action,
                "details": mapping.details_json,
            }
            for mapping in run.mappings
        ]

    @staticmethod
    def _evidence_sources(run: AnalysisRun | None) -> list[dict[str, Any]]:
        if run is None or run.startup is None:
            return []
        return [
            {
                "claim": evidence.claim,
                "source_url": evidence.source_url,
                "source_type": evidence.source_type,
                "quote_or_evidence": evidence.quote_or_evidence,
                "confidence": evidence.confidence,
                "evidence_kind": evidence.evidence_kind,
                "collected_at": evidence.collected_at.isoformat() if evidence.collected_at else None,
            }
            for evidence in run.startup.evidence
        ]

    @staticmethod
    def _source_count(run: AnalysisRun | None) -> int:
        if run is None or run.startup is None:
            return 0
        return len({
            str(evidence.source_url or "").strip()
            for evidence in (run.startup.evidence or [])
            if str(evidence.source_url or "").strip()
        })

    @staticmethod
    def _dashboard_sort_key(row: dict[str, Any]) -> tuple[float, float, float]:
        analyzed = 1.0 if row.get("row_type") == "analyzed_startup" else 0.0
        score = row.get("opportunity_score")
        score_val = float(score) if isinstance(score, (int, float)) else 0.0
        coverage = row.get("evidence_coverage")
        cov_val = float(coverage) if isinstance(coverage, (int, float)) else 0.0
        return analyzed, score_val, cov_val
