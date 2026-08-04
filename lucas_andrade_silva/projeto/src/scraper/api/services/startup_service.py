from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from scraper.api.repositories import (
    RepositoryConfigurationError,
    StartupRepository,
    SupabaseStartupRepository,
)
from scraper.enrichment_pipeline import config


SupabaseConfigurationError = RepositoryConfigurationError


class StartupNotFoundError(LookupError):
    pass


class StartupService:
    """Application rules around startup persistence."""

    _AUTOMATION_TIMEZONE = ZoneInfo("America/Bahia")
    _AUTOMATION_WEEKDAYS = {0: "Seg", 3: "Qui"}
    _AUTOMATION_CHART_POINTS = 8

    def __init__(
        self,
        repository: StartupRepository | None = None,
        candidate_repository: StartupRepository | None = None,
    ) -> None:
        table = os.getenv(
            "API_STARTUPS_TABLE", config.ENRICHMENT_RESULTS_TABLE
        )
        self.repository = repository or SupabaseStartupRepository(table)
        self.candidate_repository = (
            candidate_repository
            or SupabaseStartupRepository(config.SUPABASE_TABLE)
        )

    def list_startups(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None = None,
        validation_status: str | None = None,
        enrichment_status: str | None = None,
        ai_classification: str | None = None,
        has_nvidia_recommendation: bool = False,
    ) -> tuple[list[dict[str, Any]], int]:
        return self.repository.list(
            offset=(page - 1) * page_size,
            limit=page_size,
            search=search,
            filters={
                "validation_status": validation_status,
                "enrichment_status": enrichment_status,
                "ai_dependency_level": ai_classification,
            },
            present_filters=(
                ["nvidia_recommendation"] if has_nvidia_recommendation else None
            ),
        )

    def get_startup(self, startup_id: str) -> dict[str, Any]:
        row = self.repository.find_one("id", startup_id)
        if row is None:
            row = self.repository.find_one("candidate_id", startup_id)
        if row is None:
            candidate = self.candidate_repository.find_one("id", startup_id)
            if candidate is not None:
                enriched = self.repository.find_one(
                    "candidate_id", str(candidate["id"])
                )
                row = {**candidate, **(enriched or {})}
        if row is None:
            raise StartupNotFoundError(startup_id)
        return row

    def create_startup(self, data: dict[str, Any]) -> dict[str, Any]:
        return self.repository.create(data)

    def update_startup(
        self, startup_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        record = self.repository.find_one("id", startup_id)
        if record is None:
            record = self.repository.find_one("candidate_id", startup_id)
        if record is None:
            raise StartupNotFoundError(startup_id)
        updated = self.repository.update(str(record["id"]), data)
        if updated is None:
            raise StartupNotFoundError(startup_id)
        return updated

    def delete_startup(self, startup_id: str) -> None:
        record = self.repository.find_one("id", startup_id)
        if record is None:
            record = self.repository.find_one("candidate_id", startup_id)
        if record is None or not self.repository.delete(str(record["id"])):
            raise StartupNotFoundError(startup_id)

    def resolve_candidate_id(self, startup_id: str) -> str:
        candidate = self.candidate_repository.find_one("id", startup_id)
        if candidate is not None:
            return str(candidate["id"])
        startup = self.get_startup(startup_id)
        candidate_id = startup.get("candidate_id")
        if candidate_id:
            return str(candidate_id)
        raise StartupNotFoundError(startup_id)

    def dashboard_summary(self) -> dict[str, Any]:
        summary_counts = getattr(
            self.repository, "dashboard_summary_counts", None
        )
        if callable(summary_counts):
            summary = summary_counts()
        else:
            validation_statuses = {
                value: count
                for value in sorted(config.VALIDATION_STATUSES)
                if (count := self.repository.count("validation_status", value))
            }
            enrichment_statuses = {
                value: count
                for value in sorted(config.ENRICHMENT_STATUSES)
                if (count := self.repository.count("enrichment_status", value))
            }
            ai_classifications = {
                value: count
                for value in sorted(config.AI_DEPENDENCY_LEVELS)
                if (count := self.repository.count("ai_dependency_level", value))
            }
            try:
                recommendations_count = self.repository.count_present(
                    "nvidia_recommendation"
                )
            except Exception:
                recommendations_count = 0
            summary = {
                "total_startups": self.repository.count(),
                "validation_statuses": validation_statuses,
                "enrichment_statuses": enrichment_statuses,
                "ai_classifications": ai_classifications,
                "recommendations_count": recommendations_count,
                "github_actions_registrations": [],
            }
        candidate_ids = {
            str(value)
            for value in summary.pop("_candidate_ids", [])
            if value
        }
        classification_counts = getattr(
            self.candidate_repository, "ai_classification_counts", None
        )
        if callable(classification_counts) and candidate_ids:
            try:
                candidate_classifications = classification_counts(
                    candidate_ids
                )
                if sum(candidate_classifications.values()) == len(
                    candidate_ids
                ):
                    summary["ai_classifications"] = candidate_classifications
            except Exception:
                # Keep dependency-level counts when candidate classification
                # data is temporarily unavailable.
                pass
        generated_at = datetime.now(UTC)
        return {
            **summary,
            "github_actions_registrations": self._automation_chart_points(
                summary.get("github_actions_registrations", []),
                generated_at,
            ),
            "generated_at": generated_at,
        }

    @classmethod
    def _automation_chart_points(
        cls,
        registrations: list[dict[str, Any]],
        reference: datetime,
    ) -> list[dict[str, Any]]:
        counts = {
            str(item.get("date")): int(item.get("count") or 0)
            for item in registrations
            if item.get("date")
        }
        cursor = reference.astimezone(cls._AUTOMATION_TIMEZONE).date()
        points: list[dict[str, Any]] = []
        while len(points) < cls._AUTOMATION_CHART_POINTS:
            weekday = cls._AUTOMATION_WEEKDAYS.get(cursor.weekday())
            if weekday:
                date_key = cursor.isoformat()
                points.append(
                    {
                        "date": date_key,
                        "weekday": weekday,
                        "count": counts.get(date_key, 0),
                    }
                )
            cursor -= timedelta(days=1)
        points.reverse()
        return points
