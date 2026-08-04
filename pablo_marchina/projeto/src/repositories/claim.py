"""Claim ledger repository."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.database.models import ClaimRecord


class ClaimRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_claim(
        self,
        *,
        startup_id: str,
        analysis_run_id: str,
        claim_text: str,
        claim_type: str,
        support_level: str = "unsupported",
        confidence: str = "low",
        evidence_refs: list[dict[str, Any]] | None = None,
        used_in_score: bool = False,
        used_in_gap: bool = False,
        used_in_mapping: bool = False,
        used_in_brief: bool = False,
        review_status: str = "unreviewed",
        metadata: dict[str, Any] | None = None,
    ) -> ClaimRecord:
        record = ClaimRecord(
            startup_id=startup_id,
            analysis_run_id=analysis_run_id,
            claim_text=claim_text,
            claim_type=claim_type,
            support_level=support_level,
            confidence=confidence,
            evidence_refs_json=evidence_refs or [],
            used_in_score=used_in_score,
            used_in_gap=used_in_gap,
            used_in_mapping=used_in_mapping,
            used_in_brief=used_in_brief,
            review_status=review_status,
            metadata_json=metadata or {},
        )
        self.session.add(record)
        self.session.flush()
        return record

    def create_claims_bulk(
        self,
        claims: list[dict[str, Any]],
    ) -> list[ClaimRecord]:
        records: list[ClaimRecord] = []
        for item in claims:
            record = ClaimRecord(
                startup_id=str(item["startup_id"]),
                analysis_run_id=str(item["analysis_run_id"]),
                claim_text=str(item["claim_text"]),
                claim_type=str(item["claim_type"]),
                support_level=str(item.get("support_level", "unsupported")),
                confidence=str(item.get("confidence", "low")),
                evidence_refs_json=list(item.get("evidence_refs", [])),
                used_in_score=bool(item.get("used_in_score", False)),
                used_in_gap=bool(item.get("used_in_gap", False)),
                used_in_mapping=bool(item.get("used_in_mapping", False)),
                used_in_brief=bool(item.get("used_in_brief", False)),
                review_status=str(item.get("review_status", "unreviewed")),
                metadata_json=dict(item.get("metadata", {})),
            )
            self.session.add(record)
            records.append(record)
        self.session.flush()
        return records

    def delete_claims_for_run(self, analysis_run_id: str) -> int:
        stmt = select(ClaimRecord).where(ClaimRecord.analysis_run_id == analysis_run_id)
        existing = list(self.session.scalars(stmt))
        count = len(existing)
        for record in existing:
            self.session.delete(record)
        self.session.flush()
        return count

    def list_claims_for_analysis_run(
        self,
        analysis_run_id: str,
        *,
        claim_type: str | None = None,
        support_level: str | None = None,
        review_status: str | None = None,
    ) -> list[ClaimRecord]:
        stmt = select(ClaimRecord).where(ClaimRecord.analysis_run_id == analysis_run_id)
        if claim_type:
            stmt = stmt.where(ClaimRecord.claim_type == claim_type)
        if support_level:
            stmt = stmt.where(ClaimRecord.support_level == support_level)
        if review_status:
            stmt = stmt.where(ClaimRecord.review_status == review_status)
        stmt = stmt.order_by(ClaimRecord.created_at.desc())
        return list(self.session.scalars(stmt))

    def list_claims_for_startup(
        self,
        startup_id: str,
        *,
        claim_type: str | None = None,
        limit: int = 100,
    ) -> list[ClaimRecord]:
        stmt = select(ClaimRecord).where(ClaimRecord.startup_id == startup_id)
        if claim_type:
            stmt = stmt.where(ClaimRecord.claim_type == claim_type)
        stmt = stmt.order_by(ClaimRecord.created_at.desc()).limit(limit)
        return list(self.session.scalars(stmt))

    def get_claim(self, claim_id: str) -> ClaimRecord | None:
        return self.session.get(ClaimRecord, claim_id)

    def update_claim_review_status(
        self,
        claim_id: str,
        *,
        review_status: str,
        reviewer_notes: str = "",
    ) -> ClaimRecord | None:
        record = self.session.get(ClaimRecord, claim_id)
        if record is None:
            return None
        record.review_status = review_status
        if reviewer_notes:
            record.reviewer_notes = reviewer_notes
        record.updated_at = datetime.now(UTC)
        self.session.flush()
        return record

    def count_claims_by_support_level(
        self,
        analysis_run_id: str,
    ) -> dict[str, int]:
        stmt = (
            select(ClaimRecord.support_level, func.count(ClaimRecord.id))
            .where(ClaimRecord.analysis_run_id == analysis_run_id)
            .group_by(ClaimRecord.support_level)
        )
        result: dict[str, int] = {}
        for row in self.session.execute(stmt):
            result[str(row[0])] = int(row[1])
        return result

    def get_evidence_coverage_summary(
        self,
        analysis_run_id: str,
    ) -> dict[str, Any]:
        all_claims = self.list_claims_for_analysis_run(analysis_run_id)
        total = len(all_claims)
        if total == 0:
            return {
                "total_claims": 0,
                "supported_claims": 0,
                "unsupported_claims": 0,
                "weak_claims": 0,
                "critical_claims": 0,
                "critical_supported_claims": 0,
                "evidence_coverage": 0.0,
                "unsupported_claim_rate": 0.0,
                "avg_claim_confidence": 0.0,
            }

        from src.services.product.claim_constants import CRITICAL_CLAIM_TYPES

        supported = sum(1 for c in all_claims if c.support_level != "unsupported" and c.support_level != "weak")
        unsupported = sum(1 for c in all_claims if c.support_level == "unsupported")
        weak = sum(1 for c in all_claims if c.support_level == "weak")
        critical = sum(1 for c in all_claims if c.claim_type in CRITICAL_CLAIM_TYPES)
        critical_supported = sum(
            1
            for c in all_claims
            if c.claim_type in CRITICAL_CLAIM_TYPES and c.support_level not in ("unsupported", "weak")
        )

        confidence_map = {"high": 1.0, "medium": 0.6, "low": 0.2}
        total_confidence = sum(confidence_map.get(c.confidence, 0.2) for c in all_claims)
        avg_confidence = total_confidence / total if total > 0 else 0.0
        coverage = supported / total if total > 0 else 0.0
        unsupported_rate = unsupported / total if total > 0 else 0.0

        return {
            "total_claims": total,
            "supported_claims": supported,
            "unsupported_claims": unsupported,
            "weak_claims": weak,
            "critical_claims": critical,
            "critical_supported_claims": critical_supported,
            "evidence_coverage": round(coverage, 4),
            "unsupported_claim_rate": round(unsupported_rate, 4),
            "avg_claim_confidence": round(avg_confidence, 4),
        }

    def list_unsupported_critical_claims(
        self,
        analysis_run_id: str,
    ) -> list[ClaimRecord]:
        from src.services.product.claim_constants import CRITICAL_CLAIM_TYPES

        stmt = (
            select(ClaimRecord)
            .where(
                ClaimRecord.analysis_run_id == analysis_run_id,
                ClaimRecord.claim_type.in_(list(CRITICAL_CLAIM_TYPES)),
                ClaimRecord.support_level == "unsupported",
            )
            .order_by(ClaimRecord.created_at.desc())
        )
        return list(self.session.scalars(stmt))
