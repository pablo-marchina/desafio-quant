"""Service for building and managing Activation Dossiers from persisted records."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database.models import (
    ActivationDossierRecord,
    AnalysisRun,
)
from src.evaluation.structured_outputs import (
    readiness_check_payload_from_result,
    run_validation_with_repair,
)
from src.repositories.claim import ClaimRepository
from src.repositories.dossier import ActivationDossierRepository
from src.repositories.product import ProductRepository
from src.repositories.review import ReviewDecisionRepository
from src.services.product.activation_service import ActivationPlaybookService

logger = logging.getLogger(__name__)

_KEY_CLAIM_TYPES = (
    "gap_claim",
    "defensibility_claim",
    "nvidia_fit_claim",
    "production_readiness_claim",
)


class DossierStartupSchema(BaseModel):
    name: str = ""
    website: str = ""
    country: str = ""
    sector: str = ""
    description: str = ""
    product_summary: str = ""
    status: str = ""


class DossierExecutiveVerdictSchema(BaseModel):
    recommended_motion: str = ""
    evidence_coverage: float = 0.0
    unsupported_claim_count: int = 0


class DossierMetadataSchema(BaseModel):
    analysis_run_id: str = ""
    startup_id: str = ""
    schema_version: str = "1.0"
    dossier_version: int = 0


class DossierJsonSchema(BaseModel):
    metadata: DossierMetadataSchema = Field(default_factory=DossierMetadataSchema)
    startup: DossierStartupSchema = Field(default_factory=DossierStartupSchema)
    executive_verdict: DossierExecutiveVerdictSchema = Field(default_factory=DossierExecutiveVerdictSchema)
    scores: dict[str, Any] = Field(default_factory=dict)
    gaps: dict[str, Any] = Field(default_factory=dict)
    risks: list[dict[str, Any]] = Field(default_factory=list)
    uncertainties: list[dict[str, Any]] = Field(default_factory=list)
    review: dict[str, Any] = Field(default_factory=dict)
    next_action: dict[str, Any] = Field(default_factory=dict)


class ActivationDossierService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.dossier_repo = ActivationDossierRepository(session)
        self.product_repo = ProductRepository(session)

    def build_dossier_for_analysis_run(
        self,
        analysis_run_id: str,
        *,
        force_new_version: bool = False,
    ) -> ActivationDossierRecord:
        run = self.product_repo.get_analysis_run(analysis_run_id)
        if run is None:
            raise LookupError(f"Analysis run not found: {analysis_run_id}")

        if not force_new_version:
            existing = self.dossier_repo.get_latest_for_analysis_run(analysis_run_id)
            if existing is not None:
                return existing

        version = self.dossier_repo.next_version_for_analysis_run(analysis_run_id)
        dossier_json = self._build_dossier_json(run)
        self._validate_dossier_json(dossier_json, analysis_run_id)
        dossier_markdown = self._render_dossier_markdown(dossier_json)
        evidence_coverage = dossier_json["executive_verdict"]["evidence_coverage"]
        unsupported_claim_count = dossier_json["executive_verdict"]["unsupported_claim_count"]
        top_id = dossier_json["activation_recommendations"]["top_playbook_id"]
        recommended_motion = dossier_json["executive_verdict"]["recommended_motion"]
        review_status = dossier_json["review"]["latest_decision"]

        self.dossier_repo.mark_previous_not_latest(analysis_run_id)
        record = self.dossier_repo.create_dossier(
            analysis_run_id=analysis_run_id,
            version=version,
            schema_version="1.0",
            dossier_json=dossier_json,
            dossier_markdown=dossier_markdown,
            evidence_coverage=evidence_coverage,
            unsupported_claim_count=unsupported_claim_count,
            top_activation_playbook_id=top_id,
            recommended_motion=recommended_motion,
            review_status=review_status,
        )
        self.session.commit()
        return record

    def get_latest_dossier(self, analysis_run_id: str) -> ActivationDossierRecord | None:
        return self.dossier_repo.get_latest_for_analysis_run(analysis_run_id)

    def regenerate_dossier(self, analysis_run_id: str) -> ActivationDossierRecord:
        return self.build_dossier_for_analysis_run(analysis_run_id, force_new_version=True)

    def get_dossier_markdown(self, analysis_run_id: str) -> str | None:
        dossier = self.dossier_repo.get_latest_for_analysis_run(analysis_run_id)
        if dossier is None:
            return None
        return dossier.dossier_markdown

    def _validate_dossier_json(
        self,
        dossier_json: dict[str, Any],
        analysis_run_id: str,
    ) -> None:
        result = run_validation_with_repair(
            schema=DossierJsonSchema,
            raw_text=dossier_json,
            output_type="activation_dossier",
            schema_name="DossierJsonSchema",
            max_retries=0,
        )
        if result.status in ("invalid", "failed"):
            logger.warning(
                "Dossier JSON validation failed for run %s: %s",
                analysis_run_id,
                [str(e) for e in result.validation_errors],
            )
            try:
                from src.repositories.product import ProductRepository

                product_repo = ProductRepository(self.session)
                check_data = readiness_check_payload_from_result(result, analysis_run_id)
                if check_data:
                    product_repo.save_readiness_check(**check_data)
                    self.session.commit()
            except Exception:
                logger.exception("Failed to create readiness check for dossier validation")

    def _build_dossier_json(self, run: AnalysisRun) -> dict[str, Any]:
        startup = run.startup
        startup_data = (
            {
                "name": startup.name,
                "website": startup.website,
                "country": startup.country,
                "sector": startup.sector,
                "description": startup.description,
                "product_summary": startup.product_summary,
                "status": startup.status,
            }
            if startup is not None
            else {}
        )

        scores_data = self._collect_scores(run)
        gaps_data = self._collect_gaps(run)
        mappings_data = self._collect_mappings(run)
        claims_data = self._collect_claims(run.id)
        playbook_data = self._collect_playbook_recommendations(run.id)
        review_data = self._collect_review(run.id)
        evidence_coverage = claims_data.get("coverage", 0.0)
        unsupported = claims_data.get("unsupported_count", 0)

        uncertainties: list[dict[str, str]] = []
        risks: list[dict[str, str]] = []
        degraded_states: list[dict[str, str]] = []

        for rc in run.readiness_checks or []:
            if rc.status in ("degraded", "error"):
                degraded_states.append(
                    {
                        "code": rc.code,
                        "severity": rc.severity,
                        "message": rc.user_message,
                    }
                )
                risks.append(
                    {
                        "risk": rc.user_message,
                        "source": "degraded_state",
                        "severity": rc.severity,
                    }
                )

        if unsupported > 0:
            risks.append(
                {
                    "risk": f"{unsupported} unsupported critical claim(s) detected",
                    "source": "unsupported_claims",
                    "severity": "error",
                }
            )
            uncertainties.append(
                {
                    "description": f"{unsupported} claim(s) lack evidence support",
                    "source": "unsupported_claims",
                    "impact": "high",
                }
            )

        if evidence_coverage < 0.5:
            uncertainties.append(
                {
                    "description": f"Evidence coverage is low ({evidence_coverage:.0%})",
                    "source": "low_coverage",
                    "impact": "high",
                }
            )

        missing_evidence = list(run.output_snapshot_json.get("missing_evidence", []))
        if missing_evidence:
            uncertainties.append(
                {
                    "description": f"{len(missing_evidence)} missing evidence item(s)",
                    "source": "missing_evidence",
                    "impact": "medium",
                }
            )

        if playbook_data.get("total") == 0:
            uncertainties.append(
                {
                    "description": "No activation playbook matched diagnosed gaps",
                    "source": "no_playbook_match",
                    "impact": "medium",
                }
            )

        if review_data.get("has_review") is False:
            uncertainties.append(
                {
                    "description": "No human review has been recorded",
                    "source": "no_review",
                    "impact": "low",
                }
            )

        has_incomplete_scores = any(
            s is None
            for s in [
                scores_data.get("defensibility_score"),
                scores_data.get("inception_fit_score"),
                scores_data.get("production_readiness_score"),
            ]
        )
        if has_incomplete_scores:
            risks.append(
                {
                    "risk": "One or more required scores are missing",
                    "source": "incomplete_scores",
                    "severity": "warning",
                }
            )
            uncertainties.append(
                {
                    "description": "One or more scores are missing",
                    "source": "incomplete_scores",
                    "impact": "medium",
                }
            )

        nvidia_technologies = mappings_data.get("technologies", [])
        return {
            "metadata": {
                "analysis_run_id": run.id,
                "startup_id": run.startup_id,
                "schema_version": "1.0",
                "dossier_version": 0,
                "generated_at": datetime.now(UTC).isoformat(),
                "pipeline_version": run.pipeline_version,
                "corpus_version": run.corpus_version,
            },
            "startup": startup_data,
            "executive_verdict": {
                "recommended_motion": run.output_snapshot_json.get("recommended_motion") or "",
                "summary": self._extract_verdict_summary(run),
                "confidence": scores_data.get("composite_confidence") or "",
                "review_status": review_data.get("latest_decision"),
                "evidence_coverage": evidence_coverage,
                "unsupported_claim_count": unsupported,
            },
            "evidence_summary": {
                "evidence_count": claims_data.get("total_claims", 0),
                "top_sources": self._extract_top_sources(run),
                "coverage": evidence_coverage,
                "unsupported_claim_rate": claims_data.get("unsupported_rate", 0.0),
            },
            "claims": {
                "key_claims": claims_data.get("key_claims", []),
                "unsupported_claims": claims_data.get("unsupported_claims", []),
                "weak_claims": claims_data.get("weak_claims", []),
            },
            "scores": {
                "defensibility_score": scores_data.get("defensibility_score"),
                "inception_fit_score": scores_data.get("inception_fit_score"),
                "production_readiness_score": scores_data.get("production_readiness_score"),
                "composite_score": scores_data.get("composite_score"),
                "composite_confidence": scores_data.get("composite_confidence"),
                "missing_evidence": missing_evidence,
            },
            "gaps": {
                "detected_gaps": gaps_data.get("detected", []),
                "gap_summary": gaps_data.get("summary", ""),
            },
            "nvidia_mappings": {
                "technologies": nvidia_technologies,
                "mapping_summary": mappings_data.get("summary", ""),
            },
            "activation_recommendations": {
                "top_playbook": playbook_data.get("top"),
                "top_playbook_id": playbook_data.get("top_id"),
                "all_recommendations": playbook_data.get("all", []),
                "total": playbook_data.get("total", 0),
            },
            "suggested_experiment": playbook_data.get("experiment"),
            "risks": risks,
            "uncertainties": uncertainties,
            "review": review_data,
            "next_action": {
                "next_step": playbook_data.get("top_next_step") or "",
                "recommended_motion": run.output_snapshot_json.get("recommended_motion") or "",
                "priority": playbook_data.get("top_priority"),
            },
            "degraded_states": degraded_states,
        }

    def _collect_scores(self, run: AnalysisRun) -> dict[str, Any]:
        scores = {s.score_type: s for s in run.scores}
        result: dict[str, Any] = {}
        for score_type in ("defensibility", "inception_fit", "production_readiness"):
            s = scores.get(score_type)
            result[f"{score_type}_score"] = {"value": s.value, "confidence": s.confidence} if s else None
        composite = scores.get("composite")
        if composite:
            result["composite_score"] = composite.value
            result["composite_confidence"] = composite.confidence
        else:
            result["composite_score"] = None
            result["composite_confidence"] = None
        return result

    def _collect_gaps(self, run: AnalysisRun) -> dict[str, Any]:
        detected = [
            {
                "gap_type": g.gap_type,
                "confidence": g.confidence,
                "evidence_tag": g.evidence_tag,
                "reasoning": g.reasoning,
            }
            for g in run.gaps
            if g.detected
        ]
        summary = f"{len(detected)} gap(s) detected" if detected else "No gaps detected"
        return {"detected": detected, "summary": summary}

    def _collect_mappings(self, run: AnalysisRun) -> dict[str, Any]:
        technologies = sorted({m.technology_name for m in run.mappings})
        summary = (
            f"{len(technologies)} NVIDIA technology(ies) mapped" if technologies else "No NVIDIA technologies mapped"
        )
        return {"technologies": technologies, "summary": summary}

    def _collect_claims(self, analysis_run_id: str) -> dict[str, Any]:
        try:
            claim_repo = ClaimRepository(self.session)
            summary = claim_repo.get_evidence_coverage_summary(analysis_run_id)
            all_claims = claim_repo.list_claims_for_analysis_run(analysis_run_id)
            key_claims = [
                {
                    "claim_text": c.claim_text,
                    "claim_type": c.claim_type,
                    "support_level": c.support_level,
                    "confidence": c.confidence,
                    "review_status": c.review_status,
                }
                for c in all_claims
                if c.claim_type in _KEY_CLAIM_TYPES
            ]
            unsupported_claims = [
                {
                    "claim_text": c.claim_text,
                    "claim_type": c.claim_type,
                }
                for c in all_claims
                if c.support_level == "unsupported" and c.claim_type in _KEY_CLAIM_TYPES
            ]
            weak_claims = [
                {
                    "claim_text": c.claim_text,
                    "claim_type": c.claim_type,
                }
                for c in all_claims
                if c.support_level == "weak"
            ]
            total = summary.get("total_claims", 0)
            unsupported_count = summary.get("unsupported_claims", 0)
            unsupported_rate = unsupported_count / total if total > 0 else 0.0
            return {
                "total_claims": total,
                "coverage": summary.get("evidence_coverage", 0.0),
                "unsupported_count": unsupported_count,
                "unsupported_rate": unsupported_rate,
                "key_claims": key_claims,
                "unsupported_claims": unsupported_claims,
                "weak_claims": weak_claims,
            }
        except Exception:
            return {
                "total_claims": 0,
                "coverage": 0.0,
                "unsupported_count": 0,
                "unsupported_rate": 0.0,
                "key_claims": [],
                "unsupported_claims": [],
                "weak_claims": [],
            }

    def _collect_playbook_recommendations(self, analysis_run_id: str) -> dict[str, Any]:
        try:
            act_service = ActivationPlaybookService(self.session)
            top = act_service.get_top_for_run(analysis_run_id)
            all_recs = act_service.get_recommendations_for_run(analysis_run_id)
            experiment: dict[str, str] | None = None
            top_next_step = ""
            top_priority: int | None = None
            if top is not None:
                top_next_step = top.get("next_step", "")
                top_priority = top.get("priority")
                if top.get("technical_experiment"):
                    experiment = {
                        "title": top.get("playbook_name", ""),
                        "description": top.get("technical_experiment", ""),
                        "success_metrics": top.get("success_metrics", []),
                    }
            return {
                "top": (
                    {
                        "playbook_id": top.get("playbook_id"),
                        "playbook_name": top.get("playbook_name"),
                        "confidence": top.get("confidence"),
                        "recommended_motion": top.get("recommended_motion"),
                    }
                    if top
                    else None
                ),
                "top_id": top.get("playbook_id") if top else None,
                "top_next_step": top_next_step,
                "top_priority": top_priority,
                "all": [
                    {
                        "playbook_id": r.get("playbook_id"),
                        "playbook_name": r.get("playbook_name"),
                        "confidence": r.get("confidence"),
                        "priority": r.get("priority"),
                        "recommended_motion": r.get("recommended_motion"),
                    }
                    for r in all_recs
                ],
                "total": len(all_recs),
                "experiment": experiment,
            }
        except Exception:
            return {
                "top": None,
                "top_id": None,
                "top_next_step": "",
                "top_priority": None,
                "all": [],
                "total": 0,
                "experiment": None,
            }

    def _collect_review(self, analysis_run_id: str) -> dict[str, Any]:
        try:
            review_repo = ReviewDecisionRepository(self.session)
            all_reviews = review_repo.list_for_run(analysis_run_id)
            if not all_reviews:
                return {
                    "has_review": False,
                    "latest_decision": None,
                    "reviewer": None,
                    "notes": None,
                    "reviewed_at": None,
                    "total_reviews": 0,
                }
            latest = max(all_reviews, key=lambda r: r.created_at)
            return {
                "has_review": True,
                "latest_decision": latest.decision,
                "reviewer": latest.reviewer,
                "notes": latest.notes or None,
                "reviewed_at": latest.created_at.isoformat() if latest.created_at else None,
                "total_reviews": len(all_reviews),
            }
        except Exception:
            return {
                "has_review": False,
                "latest_decision": None,
                "reviewer": None,
                "notes": None,
                "reviewed_at": None,
                "total_reviews": 0,
            }

    def _collect_readiness_checks(self, run: AnalysisRun) -> list[dict[str, str]]:
        return [
            {
                "code": rc.code,
                "severity": rc.severity,
                "status": rc.status,
                "message": rc.user_message,
            }
            for rc in (run.readiness_checks or [])
        ]

    def _extract_verdict_summary(self, run: AnalysisRun) -> str:
        briefs = list(run.briefs)
        if not briefs:
            return ""
        latest = max(briefs, key=lambda b: b.version)
        if not latest.brief_json:
            return ""
        brief_data = latest.brief_json
        sections: list[dict[str, Any]] = brief_data.get("sections", [])
        for section in sections:
            if section.get("title") == "Executive Summary":
                content: str = section.get("content", "")
                return content
        return ""

    def _extract_top_sources(self, run: AnalysisRun) -> list[str]:
        if run.startup is None:
            return []
        sources: set[str] = set()
        for ev in run.startup.evidence:
            if ev.source_url:
                sources.add(ev.source_url)
        return sorted(sources)[:10]

    def _render_dossier_markdown(self, dossier: dict[str, Any]) -> str:
        md: list[str] = []
        md.append("# Startup Activation Dossier")
        md.append("")
        meta = dossier.get("metadata", {})
        startup_data = dossier.get("startup", {})
        name = startup_data.get("name", "N/A")
        sector = startup_data.get("sector", "N/A")
        md.append(f"**Startup:** {name} ({sector})")
        md.append(f"**Analysis Run:** {meta.get('analysis_run_id', 'N/A')}")
        md.append(f"**Generated:** {meta.get('generated_at', 'N/A')}")
        md.append(f"**Schema Version:** {meta.get('schema_version', '1.0')}")
        if meta.get("pipeline_version"):
            md.append(f"**Pipeline Version:** {meta['pipeline_version']}")
        md.append("")

        verdict = dossier.get("executive_verdict", {})
        md.append("## Executive Verdict")
        md.append("")
        md.append(f"- **Recommended Motion:** {verdict.get('recommended_motion', 'Not available')}")
        md.append(f"- **Confidence:** {verdict.get('confidence', 'Not available')}")
        md.append(f"- **Evidence Coverage:** {verdict.get('evidence_coverage', 0.0):.0%}")
        md.append(f"- **Unsupported Claims:** {verdict.get('unsupported_claim_count', 0)}")
        rs = verdict.get("review_status")
        md.append(f"- **Review Status:** {rs if rs else 'Pending review'}")
        summary = verdict.get("summary", "")
        if summary:
            md.append("")
            md.append(summary)
        md.append("")

        md.append("## Startup Profile")
        md.append("")
        md.append(f"- **Name:** {startup_data.get('name', 'N/A')}")
        md.append(f"- **Website:** {startup_data.get('website', 'N/A')}")
        md.append(f"- **Country:** {startup_data.get('country', 'N/A')}")
        md.append(f"- **Sector:** {startup_data.get('sector', 'N/A')}")
        desc = startup_data.get("description", "")
        if desc:
            md.append(f"- **Description:** {desc[:500]}")
        md.append("")

        md.append("## Evidence Summary")
        md.append("")
        es = dossier.get("evidence_summary", {})
        md.append(f"- **Total Claims:** {es.get('evidence_count', 0)}")
        md.append(f"- **Evidence Coverage:** {es.get('coverage', 0.0):.0%}")
        md.append(f"- **Unsupported Claim Rate:** {es.get('unsupported_claim_rate', 0.0):.0%}")
        top_sources = es.get("top_sources", [])
        if top_sources:
            md.append("- **Top Sources:**")
            for src in top_sources[:5]:
                md.append(f"  - {src}")
        md.append("")

        claims_section = dossier.get("claims", {})
        unsupported_list = claims_section.get("unsupported_claims", [])
        if unsupported_list:
            md.append("## Unsupported Claims ⚠️")
            md.append("")
            for c in unsupported_list:
                md.append(f"- **[{c.get('claim_type', '?')}]** {c.get('claim_text', 'N/A')}")
            md.append("")

        scores = dossier.get("scores", {})
        md.append("## Scores")
        md.append("")
        md.append("| Dimension | Value | Confidence |")
        md.append("|-----------|-------|------------|")
        for label, key in [
            ("AI-Native Defensibility", "defensibility_score"),
            ("NVIDIA Inception Fit", "inception_fit_score"),
            ("Production AI Readiness", "production_readiness_score"),
        ]:
            s = scores.get(key)
            if s and s.get("value") is not None:
                md.append(f"| {label} | {s['value']}/100 | {s.get('confidence', 'N/A')} |")
            else:
                md.append(f"| {label} | Missing | Missing |")
        cs = scores.get("composite_score")
        cc = scores.get("composite_confidence", "N/A")
        if cs is not None:
            md.append(f"| **Composite** | **{cs}/100** | **{cc}** |")
        else:
            md.append(f"| **Composite** | **Missing** | **{cc}** |")
        md.append("")

        gaps = dossier.get("gaps", {})
        detected = gaps.get("detected_gaps", [])
        if detected:
            md.append("## Gap Diagnosis")
            md.append("")
            md.append("| Gap | Confidence | Evidence Tag |")
            md.append("|-----|------------|--------------|")
            for g in detected:
                gt = g.get("gap_type", "?")
                conf = g.get("confidence", "?")
                et = g.get("evidence_tag", "?")
                md.append(f"| {gt} | {conf} | {et} |")
            md.append("")
        else:
            md.append("## Gap Diagnosis")
            md.append("")
            md.append("No gaps detected.")
            md.append("")

        mappings = dossier.get("nvidia_mappings", {})
        techs = mappings.get("technologies", [])
        if techs:
            md.append("## NVIDIA Fit")
            md.append("")
            md.append(f"**Technologies mapped:** {', '.join(techs)}")
            md.append("")

        playbooks = dossier.get("activation_recommendations", {})
        top_pb = playbooks.get("top_playbook")
        if top_pb:
            md.append("## Recommended Activation Playbook")
            md.append("")
            md.append(f"- **Playbook:** {top_pb.get('playbook_name', 'N/A')}")
            md.append(f"- **Confidence:** {top_pb.get('confidence', 'N/A')}")
            md.append(f"- **Recommended Motion:** {top_pb.get('recommended_motion', 'N/A')}")
            md.append("")
        total_pb = playbooks.get("total", 0)
        all_pb = playbooks.get("all_recommendations", [])
        if len(all_pb) > 1:
            md.append(f"**All recommendations ({total_pb} total):**")
            for pb in all_pb:
                pname = pb.get("playbook_name", "?")
                pconf = pb.get("confidence", "?")
                pprio = pb.get("priority", "?")
                md.append(f"- {pname} (confidence: {pconf}, priority: {pprio})")
            md.append("")

        experiment = playbooks.get("experiment")
        if experiment:
            md.append("## Suggested Technical Experiment")
            md.append("")
            md.append(f"- **Title:** {experiment.get('title', 'N/A')}")
            md.append(f"- **Description:** {experiment.get('description', 'N/A')}")
            metrics = experiment.get("success_metrics", [])
            if metrics:
                md.append(f"- **Success Metrics:** {', '.join(metrics)}")
            md.append("")

        risks_list = dossier.get("risks", [])
        if risks_list:
            md.append("## Risks")
            md.append("")
            for r in risks_list:
                sev = r.get("severity", "?")
                rsk = r.get("risk", "?")
                src = r.get("source", "?")
                md.append(f"- **[{sev}]** {rsk} _{src}_")
            md.append("")

        uncertainties_list = dossier.get("uncertainties", [])
        if uncertainties_list:
            md.append("## Uncertainties")
            md.append("")
            for u in uncertainties_list:
                desc = u.get("description", "?")
                imp = u.get("impact", "?")
                usrc = u.get("source", "?")
                md.append(f"- **{desc}** (impact: {imp}, source: {usrc})")
            md.append("")

        review = dossier.get("review", {})
        md.append("## Human Review")
        md.append("")
        if review.get("has_review"):
            md.append(f"- **Decision:** {review.get('latest_decision', 'N/A')}")
            md.append(f"- **Reviewer:** {review.get('reviewer', 'N/A')}")
            notes = review.get("notes")
            if notes:
                md.append(f"- **Notes:** {notes}")
            md.append(f"- **Reviewed At:** {review.get('reviewed_at', 'N/A')}")
        else:
            md.append("*No human review has been recorded for this analysis run.*")
        md.append("")

        next_action = dossier.get("next_action", {})
        md.append("## Recommended Next Step")
        md.append("")
        motion = next_action.get("recommended_motion") or verdict.get("recommended_motion", "")
        md.append(f"- **Motion:** {motion}")
        pp = next_action.get("priority")
        if pp is not None:
            md.append(f"- **Priority:** {pp}")
        ns = next_action.get("next_step") or ""
        if ns:
            md.append(f"- **Next Step:** {ns[:300]}")
        md.append("")

        md.append("---")
        md.append("")
        md.append("*Generated by NVIDIA Startup AI Radar — Activation Dossier v1.0*")

        return "\n".join(md)

    def get_dossier_summary(self, analysis_run_id: str) -> dict[str, Any]:
        dossier = self.dossier_repo.get_latest_for_analysis_run(analysis_run_id)
        if dossier is None:
            return {
                "dossier_id": None,
                "dossier_version": None,
                "dossier_available": False,
                "evidence_coverage": None,
                "unsupported_claim_count": None,
                "top_activation_playbook_id": None,
                "recommended_motion": None,
                "review_status": None,
            }
        return {
            "dossier_id": dossier.id,
            "dossier_version": dossier.version,
            "dossier_available": True,
            "evidence_coverage": dossier.evidence_coverage,
            "unsupported_claim_count": dossier.unsupported_claim_count,
            "top_activation_playbook_id": dossier.top_activation_playbook_id,
            "recommended_motion": dossier.recommended_motion,
            "review_status": dossier.review_status,
        }
