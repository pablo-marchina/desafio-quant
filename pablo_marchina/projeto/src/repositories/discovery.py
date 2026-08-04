from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from src.database.models import (
    DiscoveryRun,
    Startup,
    StartupDiscoveryCandidate,
    StartupEvidence,
)


class DiscoveryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ------------------------------------------------------------------ #
    # DiscoveryRun
    # ------------------------------------------------------------------ #

    def create_discovery_run(
        self,
        *,
        source_id: str | None = None,
        query_json: dict[str, Any] | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> DiscoveryRun:
        run = DiscoveryRun(
            source_id=source_id,
            status="queued",
            query_json=query_json or {},
            metadata_json=metadata_json or {},
        )
        self.session.add(run)
        self.session.flush()
        return run

    def update_discovery_run_status(
        self,
        run_id: str,
        *,
        status: str,
        started_at: datetime | None = None,
    ) -> DiscoveryRun:
        run = self.session.get(DiscoveryRun, run_id)
        if run is None:
            raise LookupError(f"DiscoveryRun not found: {run_id}")
        run.status = status
        if started_at is not None:
            run.started_at = started_at
        self.session.flush()
        return run

    def complete_discovery_run(
        self,
        run_id: str,
        *,
        results_count: int = 0,
        candidates_created: int = 0,
        duplicates_found: int = 0,
        metadata_json: dict[str, Any] | None = None,
    ) -> DiscoveryRun:
        run = self.session.get(DiscoveryRun, run_id)
        if run is None:
            raise LookupError(f"DiscoveryRun not found: {run_id}")
        run.status = "completed"
        run.completed_at = datetime.now(UTC)
        run.results_count = results_count
        run.candidates_created = candidates_created
        run.duplicates_found = duplicates_found
        if metadata_json:
            run.metadata_json = metadata_json
        self.session.flush()
        return run

    def fail_discovery_run(
        self,
        run_id: str,
        *,
        error_message: str,
    ) -> DiscoveryRun:
        run = self.session.get(DiscoveryRun, run_id)
        if run is None:
            raise LookupError(f"DiscoveryRun not found: {run_id}")
        run.status = "failed"
        run.completed_at = datetime.now(UTC)
        run.error_message = error_message
        self.session.flush()
        return run

    def degrade_discovery_run(
        self,
        run_id: str,
        *,
        error_message: str,
        results_count: int = 0,
        candidates_created: int = 0,
        duplicates_found: int = 0,
    ) -> DiscoveryRun:
        run = self.session.get(DiscoveryRun, run_id)
        if run is None:
            raise LookupError(f"DiscoveryRun not found: {run_id}")
        run.status = "degraded"
        run.completed_at = datetime.now(UTC)
        run.error_message = error_message
        run.results_count = results_count
        run.candidates_created = candidates_created
        run.duplicates_found = duplicates_found
        self.session.flush()
        return run

    def list_discovery_runs(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        status: str | None = None,
    ) -> list[DiscoveryRun]:
        statement: Select[tuple[DiscoveryRun]] = select(DiscoveryRun).order_by(DiscoveryRun.created_at.desc())
        if status:
            statement = statement.where(DiscoveryRun.status == status)
        statement = statement.offset(offset).limit(limit)
        return list(self.session.scalars(statement))

    def get_discovery_run(self, run_id: str) -> DiscoveryRun | None:
        return self.session.get(DiscoveryRun, run_id)

    # ------------------------------------------------------------------ #
    # StartupDiscoveryCandidate
    # ------------------------------------------------------------------ #

    def create_candidate(
        self,
        *,
        discovery_run_id: str | None = None,
        source_id: str,
        discovered_name: str,
        normalized_name: str,
        website: str = "",
        country: str = "Brazil",
        sector: str = "",
        description: str = "",
        source_url: str = "",
        raw_text_excerpt: str = "",
        ai_native_signals_json: dict[str, Any] | None = None,
        evidence_refs_json: list[dict[str, Any]] | None = None,
        confidence: str = "low",
        status: str = "new",
        metadata_json: dict[str, Any] | None = None,
    ) -> StartupDiscoveryCandidate:
        candidate = StartupDiscoveryCandidate(
            discovery_run_id=discovery_run_id,
            source_id=source_id,
            discovered_name=discovered_name,
            normalized_name=normalized_name,
            website=website,
            country=country,
            sector=sector,
            description=description,
            source_url=source_url,
            raw_text_excerpt=raw_text_excerpt,
            ai_native_signals_json=ai_native_signals_json or {},
            evidence_refs_json=evidence_refs_json or [],
            confidence=confidence,
            status=status,
            metadata_json=metadata_json or {},
        )
        self.session.add(candidate)
        self.session.flush()
        return candidate

    def create_candidates_bulk(
        self,
        candidates: list[dict[str, Any]],
    ) -> list[StartupDiscoveryCandidate]:
        models: list[StartupDiscoveryCandidate] = []
        for item in candidates:
            model = StartupDiscoveryCandidate(
                discovery_run_id=item.get("discovery_run_id"),
                source_id=str(item.get("source_id", "")),
                discovered_name=str(item.get("discovered_name", "")),
                normalized_name=str(item.get("normalized_name", "")),
                website=str(item.get("website", "")),
                country=str(item.get("country", "Brazil")),
                sector=str(item.get("sector", "")),
                description=str(item.get("description", "")),
                source_url=str(item.get("source_url", "")),
                raw_text_excerpt=str(item.get("raw_text_excerpt", "")),
                ai_native_signals_json=item.get("ai_native_signals_json") or {},
                evidence_refs_json=item.get("evidence_refs_json") or [],
                confidence=str(item.get("confidence", "low")),
                status=str(item.get("status", "new")),
                metadata_json=item.get("metadata_json") or {},
            )
            self.session.add(model)
            models.append(model)
        self.session.flush()
        return models

    def list_candidates(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        status: str | None = None,
        source_id: str | None = None,
        sector: str | None = None,
        confidence_min: float | None = None,
        has_website: bool | None = None,
        ai_native_signal: bool | None = None,
    ) -> list[StartupDiscoveryCandidate]:
        statement: Select[tuple[StartupDiscoveryCandidate]] = select(StartupDiscoveryCandidate).order_by(
            StartupDiscoveryCandidate.created_at.desc()
        )
        if status:
            statement = statement.where(StartupDiscoveryCandidate.status == status)
        if source_id:
            statement = statement.where(StartupDiscoveryCandidate.source_id == source_id)
        if sector:
            statement = statement.where(StartupDiscoveryCandidate.sector == sector)

        if confidence_min is not None:
            if confidence_min >= 0.7:
                statement = statement.where(StartupDiscoveryCandidate.confidence == "high")
            elif confidence_min >= 0.4:
                statement = statement.where(StartupDiscoveryCandidate.confidence.in_(["high", "medium"]))
        if has_website is not None:
            if has_website:
                statement = statement.where(StartupDiscoveryCandidate.website != "")
            else:
                statement = statement.where(StartupDiscoveryCandidate.website == "")
        if ai_native_signal is not None:
            if ai_native_signal:
                statement = statement.where(StartupDiscoveryCandidate.ai_native_signals_json != {})

        statement = statement.offset(offset).limit(limit)
        return list(self.session.scalars(statement))

    def get_candidate(self, candidate_id: str) -> StartupDiscoveryCandidate | None:
        return self.session.get(StartupDiscoveryCandidate, candidate_id)

    def update_candidate_status(
        self,
        candidate_id: str,
        *,
        status: str,
        metadata_json: dict[str, Any] | None = None,
    ) -> StartupDiscoveryCandidate | None:
        candidate = self.session.get(StartupDiscoveryCandidate, candidate_id)
        if candidate is None:
            return None
        candidate.status = status
        if metadata_json:
            candidate.metadata_json = metadata_json
        self.session.flush()
        return candidate

    def update_candidate_fields(
        self,
        candidate_id: str,
        fields: dict[str, Any],
    ) -> StartupDiscoveryCandidate | None:
        candidate = self.session.get(StartupDiscoveryCandidate, candidate_id)
        if candidate is None:
            return None
        for field, value in fields.items():
            if hasattr(candidate, field):
                setattr(candidate, field, value)
        self.session.flush()
        return candidate

    def mark_duplicate(
        self,
        candidate_id: str,
        *,
        duplicate_of_candidate_id: str | None = None,
        duplicate_of_startup_id: str | None = None,
    ) -> StartupDiscoveryCandidate | None:
        candidate = self.session.get(StartupDiscoveryCandidate, candidate_id)
        if candidate is None:
            return None
        candidate.status = "duplicate"
        meta = dict(candidate.metadata_json)
        if duplicate_of_candidate_id:
            meta["duplicate_of_candidate_id"] = duplicate_of_candidate_id
        if duplicate_of_startup_id:
            meta["duplicate_of_startup_id"] = duplicate_of_startup_id
        candidate.metadata_json = meta
        self.session.flush()
        return candidate

    def promote_candidate(
        self,
        candidate_id: str,
        *,
        startup_id: str,
    ) -> StartupDiscoveryCandidate | None:
        candidate = self.session.get(StartupDiscoveryCandidate, candidate_id)
        if candidate is None:
            return None
        candidate.status = "promoted"
        candidate.promoted_startup_id = startup_id
        self.session.flush()
        return candidate

    def find_duplicate_candidate(
        self,
        *,
        normalized_name: str,
        website: str,
        exclude_candidate_id: str | None = None,
    ) -> StartupDiscoveryCandidate | None:
        statement = select(StartupDiscoveryCandidate).where(
            (StartupDiscoveryCandidate.normalized_name == normalized_name)
            | (StartupDiscoveryCandidate.website == website)
        )
        if exclude_candidate_id:
            statement = statement.where(StartupDiscoveryCandidate.id != exclude_candidate_id)
        statement = statement.limit(1)
        return self.session.scalar(statement)

    def find_existing_startup_match(
        self,
        *,
        normalized_name: str,
        website: str,
    ) -> Startup | None:
        from sqlalchemy import or_
        from src.repositories.product import normalize_startup_name

        norm = normalize_startup_name(normalized_name)
        predicates = [Startup.normalized_name == norm] if norm else []
        clean_website = str(website or "").strip()
        if clean_website:
            predicates.append(Startup.website == clean_website)
        if not predicates:
            return None
        statement = select(Startup).where(or_(*predicates)).limit(1)
        return self.session.scalar(statement)

    def create_startup_from_candidate(
        self,
        candidate: StartupDiscoveryCandidate,
    ) -> Startup:
        from src.repositories.product import normalize_startup_name

        startup = Startup(
            name=candidate.discovered_name.strip(),
            normalized_name=normalize_startup_name(candidate.discovered_name),
            website=candidate.website or candidate.source_url or "",
            country=candidate.country or "Brazil",
            sector=candidate.sector or "AI",
            description=candidate.description or "",
            product_summary="",
            status="active",
            tags_json=[],
        )
        self.session.add(startup)
        self.session.flush()

        for ev in candidate.evidence_refs_json:
            evidence = StartupEvidence(
                startup_id=startup.id,
                claim=str(ev.get("signal", "Discovered via startup discovery")),
                source_url=str(ev.get("source_url", candidate.source_url)),
                source_type=str(ev.get("source_type", candidate.metadata_json.get("source_type", "directory"))),
                quote_or_evidence=str(ev.get("excerpt", candidate.raw_text_excerpt[:200])),
                confidence=candidate.confidence,
                evidence_kind="unverified",
                collected_at=datetime.now(UTC),
                metadata_json={"discovery_source_id": candidate.source_id},
            )
            self.session.add(evidence)

        self.session.flush()
        return startup
