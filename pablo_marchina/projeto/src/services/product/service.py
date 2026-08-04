"""Product orchestration over persisted startups and the existing pipeline."""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from pydantic import HttpUrl
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.briefing.action_brief import build_action_brief
from src.briefing.markdown_renderer import render_action_brief_markdown
from src.database.models import (
    ActionBriefRecord,
    AnalysisRun,
    ClaimRecord,
    ReviewDecision,
    Startup,
)
from src.database.session import (
    check_product_database,
    get_product_database,
    sanitize_database_url,
)
from src.extraction.schemas import (
    ConfidenceLevel,
    Evidence,
    SourceType,
    StartupProfile,
)
from src.rag.retrieval import build_default_index
from src.repositories.export import ExportRepository
from src.repositories.product import ProductRepository
from src.repositories.review import ReviewDecisionRepository
from src.services.product.claim_ledger import ClaimLedgerService
from src.services.product.degraded import DEGRADED_STATES
from src.services.product.export_service import ExportService
from src.services.product.opportunity_service import OpportunityService

PipelineRunner = Callable[..., Any]


_VALID_EXTRACTION_SOURCE_TYPES = {item.value for item in SourceType}

def _normalized_extraction_source_type(value: str | None) -> SourceType:
    raw = (value or "").strip().casefold()
    aliases = {
        "web": SourceType.DIRECTORY,
        "manual_seed": SourceType.DIRECTORY,
        "official_website": SourceType.OFFICIAL_SITE,
        "website": SourceType.OFFICIAL_SITE,
        "social": SourceType.FOUNDER_PROFILE,
        "social_media": SourceType.FOUNDER_PROFILE,
    }
    if raw in aliases:
        return aliases[raw]
    if raw in _VALID_EXTRACTION_SOURCE_TYPES:
        return SourceType(raw)
    return SourceType.DIRECTORY

def _safe_http_url(primary: str | None, fallback: str | None = None) -> HttpUrl | None:
    for raw in (primary, fallback):
        value = (raw or "").strip()
        if not value:
            continue
        try:
            return HttpUrl(value)
        except Exception:
            continue
    return None


class ProductService:
    def __init__(
        self,
        session: Session,
        *,
        pipeline_runner: PipelineRunner | None = None,
    ) -> None:
        self.session = session
        self.repository = ProductRepository(session)
        if pipeline_runner is None and os.getenv("APP_MODE", "").casefold() != "product":
            from src.pipeline.run_pipeline import run_full_pipeline

            pipeline_runner = run_full_pipeline
        self.pipeline_runner = pipeline_runner

    def create_startup(self, payload: dict[str, Any]) -> Startup:
        try:
            startup = self.repository.create_startup(
                name=str(payload["name"]),
                website=str(payload["website"]),
                country=str(payload.get("country", "Brazil")),
                sector=str(payload["sector"]),
                description=str(payload.get("description", "")),
                product_summary=str(payload.get("product_summary", "")),
                status=str(payload.get("status", "active")),
                tags=list(payload.get("tags", [])),
            )
            for item in payload.get("evidence", []):
                self.repository.add_evidence(
                    startup_id=startup.id,
                    claim=str(item["claim"]),
                    source_url=str(item["source_url"]),
                    source_type=self._enum_value(item["source_type"]),
                    quote_or_evidence=str(item["quote_or_evidence"]),
                    confidence=self._enum_value(item["confidence"]),
                    evidence_kind=self._enum_value(item.get("evidence_kind", "unverified")),
                    collected_at=item.get("collected_at") or datetime.now(UTC),
                    metadata=dict(item.get("metadata", {})),
                )
            self.session.commit()
            return self.repository.get_startup(startup.id) or startup
        except IntegrityError:
            self.session.rollback()
            raise ValueError("A startup with this normalized name already exists.") from None

    def list_startups(self, *, offset: int = 0, limit: int = 100) -> list[Startup]:
        return self.repository.list_startups(offset=offset, limit=limit)

    def get_startup(self, startup_id: str) -> Startup | None:
        return self.repository.get_startup(startup_id)

    def create_analysis_run_for_startup(
        self,
        startup_id: str,
        *,
        use_rag: bool = False,
        rag_backend: str = "qdrant",
        pipeline_version: str = "current",
        corpus_version: str | None = None,
    ) -> AnalysisRun:
        startup = self.repository.get_startup(startup_id)
        if startup is None:
            raise LookupError(f"Startup not found: {startup_id}")
        if os.getenv("APP_MODE", "").casefold() == "product":
            if self._env_bool("RAG_REQUIRED_FOR_PRODUCT", False) and not use_rag:
                raise ValueError("APP_MODE=product requires use_rag=true.")
            if use_rag and rag_backend != "qdrant":
                raise ValueError("APP_MODE=product requires rag_backend='qdrant'.")

        input_snapshot = self._startup_input_snapshot(startup)
        config_snapshot = {
            "use_rag": use_rag,
            "rag_backend": rag_backend,
            "rag_required": self._env_bool("RAG_REQUIRED_FOR_PRODUCT", False),
        }
        run = self.repository.create_analysis_run(
            startup_id=startup.id,
            input_snapshot=input_snapshot,
            pipeline_version=pipeline_version,
            corpus_version=corpus_version or self._current_corpus_version(),
            config_snapshot=config_snapshot,
        )
        self.session.commit()

        self.repository.update_analysis_run_status(run.id, status="running", started_at=datetime.now(UTC))
        self.session.commit()

        if self.pipeline_runner is None:
            from src.orchestration.service import WorkflowOrchestrationService
            from src.orchestration.result_adapter import workflow_state_to_output_snapshot

            try:
                orch = WorkflowOrchestrationService(self.session)
                state = orch.create_and_run_workflow(
                    startup_id=startup.id,
                    analysis_run_id=run.id,
                    use_rag=use_rag,
                )
                final_status = "completed"
                error_message = None
                degraded_reason = None
                if state.status == "awaiting_review" or state.review_required:
                    final_status = "awaiting_review"
                elif state.error_message:
                    final_status = "failed"
                    error_message = state.error_message
                elif state.degraded_nodes:
                    final_status = "degraded"
                    degraded_reason = ", ".join(dict.fromkeys(state.degraded_nodes))
                self.repository.update_analysis_run_status(
                    run.id,
                    status=final_status,
                    completed_at=None if final_status == "awaiting_review" else datetime.now(UTC),
                    error_message=error_message,
                    degraded_reason=degraded_reason,
                    output_snapshot=workflow_state_to_output_snapshot(state),
                )
                self.session.commit()
                return self.repository.get_analysis_run(run.id) or run
            except Exception as exc:
                self.session.rollback()
                failed = self.repository.update_analysis_run_status(
                    run.id,
                    status="failed",
                    completed_at=datetime.now(UTC),
                    error_message=str(exc),
                )
                self.session.commit()
                return self.repository.get_analysis_run(failed.id) or failed

        degraded_codes: list[str] = []
        try:
            chunk_index = None
            embedding_model = None
            vector_store = None
            if use_rag:
                chunk_index = build_default_index()
                if not chunk_index.chunks:
                    degraded_codes.append("RAG_UNAVAILABLE")
                    self._save_degraded_check(
                        run.id,
                        "RAG_UNAVAILABLE",
                        "The configured NVIDIA corpus produced an empty retrieval index.",
                    )
                    if self._env_bool("RAG_REQUIRED_FOR_PRODUCT", False):
                        raise RuntimeError("RAG is required but the corpus index is empty.")

                if rag_backend == "qdrant":
                    try:
                        vector_store = self._build_qdrant_store()
                    except Exception as exc:
                        qdrant_detail = str(exc)
                        degraded_codes.append("QDRANT_UNAVAILABLE")
                        self._save_degraded_check(run.id, "QDRANT_UNAVAILABLE", qdrant_detail)
                        if self._env_bool("RAG_REQUIRED_FOR_PRODUCT", False):
                            raise RuntimeError(qdrant_detail or "Qdrant is required but unavailable.") from exc
                    if vector_store is not None:
                        try:
                            embedding_model = self._build_embedding_model()
                        except Exception as exc:
                            degraded_codes.append("RAG_UNAVAILABLE")
                            self._save_degraded_check(run.id, "RAG_UNAVAILABLE", str(exc))
                            vector_store = None
                            if self._env_bool("RAG_REQUIRED_FOR_PRODUCT", False):
                                raise RuntimeError(str(exc)) from exc

            profile, evidence = self._pipeline_inputs(startup)
            result = self.pipeline_runner(
                startup_name=startup.name,
                profile=profile,
                evidence_list=evidence,
                chunk_index=chunk_index,
                embedding_model=embedding_model,
                vector_store=vector_store,
            )
            output_snapshot = result.model_dump(mode="json")
            self._persist_pipeline_result(run.id, startup.id, result)

            ledger = ClaimLedgerService(self.session)
            run_for_claims = self.repository.get_analysis_run(run.id)
            if run_for_claims is not None:
                ledger.persist_claims_for_run(run_for_claims)
                claim_issues = ledger.detect_unsupported_claims(run.id)
                for issue in claim_issues:
                    code = issue["code"]
                    if code not in dict.fromkeys(degraded_codes):
                        degraded_codes.append(code)
                        self._save_degraded_check(
                            run.id,
                            code,
                            issue["detail"],
                            metadata={"claim_ids": issue.get("claim_ids", [])},
                        )

            try:
                from src.services.product.activation_service import ActivationPlaybookService

                act_service = ActivationPlaybookService(self.session)
                playbook_recs = act_service.generate_recommendations_for_run(run.id)
                if playbook_recs:
                    act_service.activation_repo.replace_recommendations_for_analysis_run(run.id, playbook_recs)
                    low_conf = any(r["confidence"] == "low" for r in playbook_recs)
                    has_unsupported = any(
                        r["confidence"] == "low" and len(r.get("matched_gap_types", [])) > 0 for r in playbook_recs
                    )
                    if low_conf:
                        degraded_codes.append("PLAYBOOK_LOW_EVIDENCE_SUPPORT")
                        self._save_degraded_check(
                            run.id,
                            "PLAYBOOK_LOW_EVIDENCE_SUPPORT",
                            "Playbook recommendations have low confidence due to weak evidence.",
                        )
                    if has_unsupported:
                        degraded_codes.append("PLAYBOOK_UNSUPPORTED_CLAIMS")
                        self._save_degraded_check(
                            run.id,
                            "PLAYBOOK_UNSUPPORTED_CLAIMS",
                            "Playbook matched but critical claims lack evidence support.",
                        )
                else:
                    degraded_codes.append("NO_ACTIVATION_PLAYBOOK_MATCH")
                    self._save_degraded_check(
                        run.id,
                        "NO_ACTIVATION_PLAYBOOK_MATCH",
                        "No activation playbook matched the diagnosed gaps for this run.",
                    )
            except Exception:
                pass

            if result.missing_evidence:
                degraded_codes.append("MISSING_EVIDENCE")
                self._save_degraded_check(
                    run.id,
                    "MISSING_EVIDENCE",
                    f"{len(result.missing_evidence)} missing evidence item(s).",
                    metadata={"missing_evidence": result.missing_evidence},
                )
            if use_rag and result.rag_output is not None and result.rag_output.missing_context:
                if "RAG_UNAVAILABLE" not in degraded_codes:
                    degraded_codes.append("RAG_UNAVAILABLE")
                    self._save_degraded_check(
                        run.id,
                        "RAG_UNAVAILABLE",
                        result.rag_output.rag_quality_summary,
                    )

            final_status = "degraded" if degraded_codes else "completed"
            updated = self.repository.update_analysis_run_status(
                run.id,
                status=final_status,
                completed_at=datetime.now(UTC),
                degraded_reason=", ".join(dict.fromkeys(degraded_codes)) or None,
                output_snapshot=output_snapshot,
            )
            self.session.commit()
            return self.repository.get_analysis_run(updated.id) or updated
        except Exception as exc:
            self.session.rollback()
            for code in dict.fromkeys(degraded_codes):
                self._save_degraded_check(run.id, code, str(exc))
            failed = self.repository.update_analysis_run_status(
                run.id,
                status="failed",
                completed_at=datetime.now(UTC),
                error_message=str(exc),
                degraded_reason=", ".join(dict.fromkeys(degraded_codes)) or None,
            )
            self.session.commit()
            return self.repository.get_analysis_run(failed.id) or failed

    def get_analysis_run(self, analysis_run_id: str) -> AnalysisRun | None:
        return self.repository.get_analysis_run(analysis_run_id)

    def get_action_brief_for_run(self, analysis_run_id: str) -> ActionBriefRecord | None:
        return self.repository.get_latest_action_brief(analysis_run_id)

    def update_startup(self, startup_id: str, fields: dict[str, Any]) -> Startup:
        from src.repositories.product import normalize_startup_name

        if "name" in fields:
            new_normalized = normalize_startup_name(str(fields["name"]))
            existing = self.repository.get_startup(startup_id)
            if existing is not None:
                conflict = self.session.execute(
                    __import__("sqlalchemy")
                    .select(Startup)
                    .where(
                        Startup.normalized_name == new_normalized,
                        Startup.id != startup_id,
                    )
                ).scalar()
                if conflict is not None:
                    raise ValueError("A startup with this normalized name already exists.")

        updated = self.repository.update_startup_fields(startup_id, fields)
        if updated is None:
            raise LookupError(f"Startup not found: {startup_id}")
        self.session.commit()
        return updated

    def create_review(
        self,
        analysis_run_id: str,
        *,
        decision: str,
        reviewer: str,
        notes: str = "",
        metadata: dict | None = None,
    ) -> ReviewDecision:
        run = self.repository.get_analysis_run(analysis_run_id)
        if run is None:
            raise LookupError(f"Analysis run not found: {analysis_run_id}")
        review_repo = ReviewDecisionRepository(self.session)
        record = review_repo.create(
            analysis_run_id=analysis_run_id,
            startup_id=run.startup_id,
            decision=decision,
            reviewer=reviewer,
            notes=notes,
            metadata=metadata,
        )
        self.session.commit()
        return record

    def list_reviews(self, analysis_run_id: str) -> list[ReviewDecision]:
        review_repo = ReviewDecisionRepository(self.session)
        return review_repo.list_for_run(analysis_run_id)

    def list_opportunities(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        status: str | None = None,
        recommended_motion: str | None = None,
        min_score: float | None = None,
        sector: str | None = None,
        has_degraded: bool | None = None,
        review_decision: str | None = None,
        order_by: str = "inception_fit_score",
    ) -> tuple[list[dict], int]:
        svc = OpportunityService(self.session)
        return svc.list_opportunities(
            offset=offset,
            limit=limit,
            status=status,
            recommended_motion=recommended_motion,
            min_score=min_score,
            sector=sector,
            has_degraded=has_degraded,
            review_decision=review_decision,
            order_by=order_by,
        )

    def get_claims_for_analysis_run(
        self,
        analysis_run_id: str,
        *,
        claim_type: str | None = None,
        support_level: str | None = None,
        review_status: str | None = None,
    ) -> list:
        ledger = ClaimLedgerService(self.session)
        return ledger.get_claims_for_analysis_run(
            analysis_run_id,
            claim_type=claim_type,
            support_level=support_level,
            review_status=review_status,
        )

    def get_evidence_coverage_for_analysis_run(
        self,
        analysis_run_id: str,
    ) -> dict:
        ledger = ClaimLedgerService(self.session)
        return ledger.get_evidence_coverage_for_analysis_run(analysis_run_id)

    def update_claim_review(
        self,
        claim_id: str,
        *,
        review_status: str,
        reviewer_notes: str = "",
    ) -> ClaimRecord | None:
        ledger = ClaimLedgerService(self.session)
        return ledger.update_claim_review(
            claim_id,
            review_status=review_status,
            reviewer_notes=reviewer_notes,
        )

    def create_export(self, analysis_run_id: str, export_type: str) -> Any:
        export_svc = ExportService(
            repository=ExportRepository(self.session),
            product_repo=self.repository,
        )
        try:
            return export_svc.create_export(analysis_run_id, export_type)
        except LookupError:
            raise

    def get_export(self, export_id: str) -> Any:
        export_svc = ExportService(
            repository=ExportRepository(self.session),
            product_repo=self.repository,
        )
        return export_svc.get_export(export_id)

    def get_product_health(self) -> dict[str, Any]:
        enabled = self._env_bool("ENABLE_PRODUCT_PERSISTENCE", True)
        database_ok, error = check_product_database()
        tables: list[str] = []
        if database_ok:
            tables = sorted(inspect(get_product_database().engine).get_table_names())
        required_tables = {
            "startups",
            "startup_evidence",
            "analysis_runs",
            "score_records",
            "gap_diagnosis_records",
            "nvidia_mapping_records",
            "action_brief_records",
            "product_readiness_checks",
            "claim_records",
        }
        schema_ready = required_tables.issubset(tables)
        status = "ok" if enabled and database_ok and schema_ready else "degraded"
        try:
            configured_url = (
                get_product_database().url
                if database_ok
                else os.getenv("PRODUCT_DB_URL", "sqlite:///data/product/product.db")
            )
            database_url = sanitize_database_url(configured_url)
        except Exception:
            database_url = "invalid"
        return {
            "status": status,
            "app_mode": os.getenv("APP_MODE", "product"),
            "product_persistence_enabled": enabled,
            "database_available": database_ok,
            "schema_ready": schema_ready,
            "database_url": database_url,
            "error": error,
        }

    def get_dependency_health(self) -> dict[str, Any]:
        database_ok, database_error = check_product_database()
        qdrant_configured = bool(os.getenv("QDRANT_URL", "http://localhost:6333"))
        qdrant_ok, qdrant_error = self._check_qdrant() if qdrant_configured else (False, None)
        corpus_version = self._current_corpus_version()
        rag_configured = bool(corpus_version)
        dependencies = [
            {
                "name": "product_database",
                "configured": True,
                "available": database_ok,
                "required": True,
                "status": "ok" if database_ok else "error",
                "detail": database_error,
            },
            {
                "name": "qdrant",
                "configured": qdrant_configured,
                "available": qdrant_ok,
                "required": self._env_bool("RAG_REQUIRED_FOR_PRODUCT", False),
                "status": "ok" if qdrant_ok else "degraded",
                "detail": qdrant_error,
            },
            {
                "name": "rag_corpus",
                "configured": rag_configured,
                "available": rag_configured,
                "required": self._env_bool("RAG_REQUIRED_FOR_PRODUCT", False),
                "status": "ok" if rag_configured else "degraded",
                "detail": f"corpus_version={corpus_version}" if corpus_version else None,
            },
        ]
        required_unavailable = any(item["required"] and not item["available"] for item in dependencies)
        optional_unavailable = any(item["configured"] and not item["available"] for item in dependencies)
        return {
            "status": ("error" if required_unavailable else "degraded" if optional_unavailable else "ok"),
            "corpus_version": corpus_version,
            "dependencies": dependencies,
        }

    def _pipeline_inputs(self, startup: Startup) -> tuple[StartupProfile, list[Evidence]]:
        evidence: list[Evidence] = []
        for item in startup.evidence:
            source_url = _safe_http_url(item.source_url, startup.website)
            if source_url is None:
                continue
            confidence_raw = (item.confidence or "low").strip().casefold()
            if confidence_raw not in {level.value for level in ConfidenceLevel}:
                confidence_raw = "low"
            evidence.append(
                Evidence(
                    claim=item.claim,
                    source_url=source_url,
                    source_type=_normalized_extraction_source_type(item.source_type),
                    quote_or_evidence=item.quote_or_evidence,
                    confidence=ConfidenceLevel(confidence_raw),
                    collected_at=item.collected_at,
                )
            )
        evidence_texts = [f"{item.claim} {item.quote_or_evidence}" for item in startup.evidence]
        confidence_score = (
            sum(
                {
                    ConfidenceLevel.HIGH.value: 1.0,
                    ConfidenceLevel.MEDIUM.value: 0.6,
                    ConfidenceLevel.LOW.value: 0.2,
                }.get(item.confidence, 0.2)
                for item in startup.evidence
            )
            / len(startup.evidence)
            if startup.evidence
            else 0.0
        )
        profile = StartupProfile(
            startup_name=startup.name,
            website=HttpUrl(startup.website),
            country=startup.country,
            sector=startup.sector,
            description=startup.description,
            product_summary=startup.product_summary,
            ai_signals=self._signals_matching(
                evidence_texts,
                ("ai", "llm", "model", "inference", "guardrails", "optimization", "telemetry"),
            ),
            customers=self._signals_matching(evidence_texts, ("customer", "enterprise", "production traffic")),
            funding_signals=self._signals_matching(evidence_texts, ("funding", "raised", "series a", "series b")),
            tech_stack_signals=self._signals_matching(
                evidence_texts,
                ("cuda", "tensorrt", "triton", "kubernetes", "docker", "kafka", "spark", "pytorch"),
            ),
            sources=evidence,
            confidence_score=confidence_score,
        )
        return profile, evidence

    @staticmethod
    def _signals_matching(texts: list[str], keywords: tuple[str, ...]) -> list[str]:
        matches: list[str] = []
        for text in texts:
            lower = text.lower()
            if any(keyword in lower for keyword in keywords):
                matches.append(text)
        return matches

    def _persist_pipeline_result(
        self,
        analysis_run_id: str,
        startup_id: str,
        result: PipelineResult,
    ) -> None:
        validated = result.validated_evidence
        self.repository.sync_validated_evidence(
            startup_id=startup_id,
            validated_evidence=[item.model_dump(mode="json") for item in validated],
        )

        score_specs = [
            (
                "defensibility",
                result.defensibility_score.total_score,
                result.defensibility_score,
                result.defensibility_score.missing_evidence,
            ),
            (
                "inception_fit",
                result.inception_fit_score.total_score,
                result.inception_fit_score,
                result.inception_fit_score.missing_evidence,
            ),
            (
                "production_readiness",
                result.production_readiness_score.production_readiness_score,
                result.production_readiness_score,
                result.production_readiness_score.missing_evidence,
            ),
            (
                "composite",
                result.composite_score.composite_score,
                result.composite_score,
                result.composite_score.missing_components,
            ),
        ]
        for score_type, value, score_model, missing in score_specs:
            score_data = score_model.model_dump(mode="json")
            self.repository.save_score(
                analysis_run_id=analysis_run_id,
                score_type=score_type,
                value=value,
                confidence=str(score_data.get("confidence", "low")),
                components=score_data,
                missing_evidence=list(missing),
            )

        gap_records: dict[str, str] = {}
        if result.gap_diagnosis is not None:
            for gap in result.gap_diagnosis.diagnosed_gaps:
                gap_data = gap.model_dump(mode="json")
                record = self.repository.save_gap(
                    analysis_run_id=analysis_run_id,
                    gap_type=str(gap_data["gap"]),
                    detected=gap.detected,
                    confidence=str(gap_data["confidence"]),
                    evidence_tag=str(gap_data["evidence_tag"]),
                    reasoning=gap.reasoning,
                    evidence_refs=[item.model_dump(mode="json") for item in gap.evidence_used],
                )
                gap_records[str(gap_data["gap"])] = record.id

            recommendations = {}
            if result.recommendation is not None:
                recommendations = {item.diagnosed_gap.value: item for item in result.recommendation.recommendations}
            for mapping in result.gap_diagnosis.nvidia_technology_candidates:
                gap_type = mapping.addresses_gap.value
                recommendation = recommendations.get(gap_type)
                details = recommendation.model_dump(mode="json") if recommendation is not None else {}
                if result.rag_output is not None:
                    details["rag_support_refs"] = self._rag_support_refs(
                        result.rag_output,
                        gap_type=gap_type,
                        technology_name=mapping.technology_name,
                    )
                self.repository.save_mapping(
                    analysis_run_id=analysis_run_id,
                    gap_record_id=gap_records.get(gap_type),
                    technology_name=mapping.technology_name,
                    addresses_gap=gap_type,
                    justification=mapping.justification,
                    recommendation_action=(recommendation.action.value if recommendation is not None else None),
                    priority=(recommendation.priority.value if recommendation is not None else None),
                    details=details,
                )

        brief = build_action_brief(result)
        self.repository.save_action_brief(
            analysis_run_id=analysis_run_id,
            version=1,
            schema_version="2.0",
            brief_json=brief.model_dump(mode="json"),
            brief_markdown=render_action_brief_markdown(brief),
        )

    def _save_degraded_check(
        self,
        analysis_run_id: str | None,
        code: str,
        internal_detail: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        definition = DEGRADED_STATES[code]
        self.repository.save_readiness_check(
            analysis_run_id=analysis_run_id,
            code=definition.code,
            severity=definition.severity,
            status="degraded",
            user_message=definition.user_message,
            internal_detail=internal_detail,
            recommended_action=definition.recommended_action,
            metadata=metadata,
        )

    @staticmethod
    def _rag_support_refs(
        rag_output: Any,
        *,
        gap_type: str,
        technology_name: str,
    ) -> list[dict[str, Any]]:
        packing = getattr(rag_output, "packing_result", None)
        packed = getattr(packing, "packed", []) if packing is not None else []
        refs: list[dict[str, Any]] = []
        tech_lower = technology_name.lower()
        for ctx in packed:
            matched_gap = getattr(ctx, "matched_gap", None)
            matched_technology = getattr(ctx, "matched_technology", None)
            product = getattr(ctx, "product", "")
            if matched_gap not in (None, gap_type):
                continue
            if (
                matched_technology
                and matched_technology.lower() not in tech_lower
                and tech_lower not in matched_technology.lower()
            ):
                continue
            if (
                not matched_technology
                and product
                and product.lower() not in tech_lower
                and tech_lower not in product.lower()
            ):
                continue
            refs.append(
                {
                    "chunk_id": getattr(ctx, "chunk_id", ""),
                    "source_id": getattr(ctx, "source_id", ""),
                    "title": getattr(ctx, "title", ""),
                    "source_url": getattr(ctx, "url", None),
                    "claim": f"NVIDIA corpus supports {technology_name} for {gap_type}",
                    "confidence": "medium",
                    "matched_gap": matched_gap,
                    "matched_technology": matched_technology or product,
                }
            )
        return refs

    @staticmethod
    def _startup_input_snapshot(startup: Startup) -> dict[str, Any]:
        return {
            "startup": {
                "id": startup.id,
                "name": startup.name,
                "website": startup.website,
                "country": startup.country,
                "sector": startup.sector,
                "description": startup.description,
                "product_summary": startup.product_summary,
                "status": startup.status,
                "tags": startup.tags_json,
            },
            "evidence": [
                {
                    "id": item.id,
                    "claim": item.claim,
                    "source_url": item.source_url,
                    "source_type": item.source_type,
                    "quote_or_evidence": item.quote_or_evidence,
                    "confidence": item.confidence,
                    "evidence_kind": item.evidence_kind,
                    "collected_at": item.collected_at.isoformat(),
                }
                for item in startup.evidence
            ],
        }

    @staticmethod
    def _env_bool(name: str, default: bool) -> bool:
        raw = os.getenv(name)
        if raw is None:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _enum_value(value: Any) -> str:
        enum_value = getattr(value, "value", value)
        return str(enum_value)

    @staticmethod
    def _check_qdrant() -> tuple[bool, str | None]:
        try:
            from qdrant_client import QdrantClient

            client = QdrantClient(
                url=os.getenv("QDRANT_URL", "http://localhost:6333"),
                api_key=os.getenv("QDRANT_API_KEY") or None,
                timeout=5,
            )
            client.get_collections()
            return True, None
        except Exception as exc:
            return False, str(exc)

    @staticmethod
    def _build_qdrant_store() -> Any:
        from src.rag.qdrant_store import QdrantConfig, QdrantStore

        config = QdrantConfig(
            url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            api_key=os.getenv("QDRANT_API_KEY") or None,
            collection_name=os.getenv("QDRANT_COLLECTION", "nvidia_corpus"),
            vector_size=int(os.getenv("QDRANT_VECTOR_SIZE", "384")),
        )
        store = QdrantStore(config=config)
        store._ensure_client()
        return store

    @staticmethod
    def _build_embedding_model() -> Any:
        from src.rag.embeddings import SentenceTransformerProvider

        return SentenceTransformerProvider(
            os.getenv(
                "RAG_EMBEDDING_MODEL",
                "sentence-transformers/all-MiniLM-L6-v2",
            )
        )

    @staticmethod
    def _current_corpus_version() -> str | None:
        try:
            from src.rag.ingestion import load_sources

            versions = sorted(
                {source.version for source in load_sources().values() if source.is_active and source.version}
            )
            return ",".join(versions) if versions else None
        except Exception:
            return None
