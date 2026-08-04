from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from scraper.enrichment_pipeline import config


class SupabaseConfigurationError(RuntimeError):
    pass


class StartupNotFoundError(LookupError):
    pass


class SupabaseService:
    """Read-only access used by the API; Supabase remains the source of truth."""

    def __init__(
        self,
        table: str | None = None,
        candidate_table: str | None = None,
    ) -> None:
        self.table = table or os.getenv(
            "API_STARTUPS_TABLE", config.ENRICHMENT_RESULTS_TABLE
        )
        self.candidate_table = candidate_table or config.SUPABASE_TABLE
        self.timeout = float(os.getenv("API_SUPABASE_TIMEOUT", "15"))
        self._validate_table(self.table)
        self._validate_table(self.candidate_table)

    @staticmethod
    def _validate_table(table: str) -> None:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
            raise ValueError(f"Invalid Supabase table name: {table}")

    def _has_rest_credentials(self) -> bool:
        return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY"))

    def _headers(self, *, count: bool = False) -> dict[str, str]:
        key = os.getenv("SUPABASE_KEY")
        if not key:
            raise SupabaseConfigurationError("SUPABASE_KEY is not configured")
        headers = {"apikey": key, "Authorization": f"Bearer {key}"}
        if count:
            headers["Prefer"] = "count=exact"
        return headers

    def _rest_get(
        self,
        table: str,
        params: dict[str, Any],
        *,
        count: bool = False,
    ) -> httpx.Response:
        base_url = os.getenv("SUPABASE_URL")
        if not base_url:
            raise SupabaseConfigurationError("SUPABASE_URL is not configured")
        response = httpx.get(
            f"{base_url.rstrip('/')}/rest/v1/{table}",
            params=params,
            headers=self._headers(count=count),
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response

    @staticmethod
    def _parse_total(response: httpx.Response, fallback: int) -> int:
        content_range = response.headers.get("content-range", "")
        try:
            return int(content_range.rsplit("/", 1)[1])
        except (IndexError, ValueError):
            return fallback

    @staticmethod
    def _connection():
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise SupabaseConfigurationError(
                "Configure SUPABASE_URL/SUPABASE_KEY or DATABASE_URL"
            )
        import psycopg2

        return psycopg2.connect(database_url)

    def list_startups(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None = None,
        validation_status: str | None = None,
        enrichment_status: str | None = None,
        ai_classification: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        offset = (page - 1) * page_size
        filters = {
            "validation_status": validation_status,
            "enrichment_status": enrichment_status,
            "ai_dependency_level": ai_classification,
        }
        if self._has_rest_credentials():
            params: dict[str, Any] = {
                "select": "*",
                "order": "updated_at.desc.nullslast",
                "offset": str(offset),
                "limit": str(page_size),
            }
            if search:
                params["company_name"] = f"ilike.*{search}*"
            for field, value in filters.items():
                if value:
                    params[field] = f"eq.{value}"
            response = self._rest_get(self.table, params, count=True)
            payload = response.json()
            rows = list(payload if isinstance(payload, list) else [])
            return rows, self._parse_total(response, len(rows))

        clauses: list[str] = []
        values: list[Any] = []
        if search:
            clauses.append("company_name ILIKE %s")
            values.append(f"%{search}%")
        for field, value in filters.items():
            if value:
                clauses.append(f"{field} = %s")
                values.append(value)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM {self.table}{where}", values)
                total = int(cursor.fetchone()[0])
                cursor.execute(
                    f"SELECT * FROM {self.table}{where} "
                    "ORDER BY updated_at DESC NULLS LAST LIMIT %s OFFSET %s",
                    [*values, page_size, offset],
                )
                columns = [column[0] for column in cursor.description]
                rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return rows, total

    def _find_one(
        self, table: str, field: str, value: str
    ) -> dict[str, Any] | None:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", field):
            raise ValueError("Invalid field")
        if self._has_rest_credentials():
            response = self._rest_get(
                table,
                {"select": "*", field: f"eq.{value}", "limit": "1"},
            )
            payload = response.json()
            return dict(payload[0]) if isinstance(payload, list) and payload else None
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT * FROM {table} WHERE {field} = %s LIMIT 1",
                    (value,),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                columns = [column[0] for column in cursor.description]
                return dict(zip(columns, row))

    def get_startup(self, startup_id: str) -> dict[str, Any]:
        row = self._find_one(self.table, "id", startup_id)
        if row is None:
            row = self._find_one(self.table, "candidate_id", startup_id)
        if row is None:
            candidate = self._find_one(self.candidate_table, "id", startup_id)
            if candidate is not None:
                enriched = self._find_one(
                    self.table, "candidate_id", str(candidate["id"])
                )
                row = {**candidate, **(enriched or {})}
        if row is None:
            raise StartupNotFoundError(startup_id)
        return row

    def resolve_candidate_id(self, startup_id: str) -> str:
        candidate = self._find_one(self.candidate_table, "id", startup_id)
        if candidate is not None:
            return str(candidate["id"])
        startup = self.get_startup(startup_id)
        candidate_id = startup.get("candidate_id")
        if candidate_id:
            return str(candidate_id)
        raise StartupNotFoundError(startup_id)

    def _count(self, field: str | None = None, value: str | None = None) -> int:
        if field is not None and not re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_]*", field
        ):
            raise ValueError("Invalid field")
        if self._has_rest_credentials():
            params: dict[str, Any] = {"select": "id", "limit": "1"}
            if field and value is not None:
                params[field] = f"eq.{value}"
            response = self._rest_get(self.table, params, count=True)
            return self._parse_total(response, 0)
        where = f" WHERE {field} = %s" if field else ""
        params = (value,) if field else ()
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT COUNT(*) FROM {self.table}{where}", params
                )
                return int(cursor.fetchone()[0])

    def dashboard_summary(self) -> dict[str, Any]:
        validation_statuses = {
            status: count
            for status in sorted(config.VALIDATION_STATUSES)
            if (count := self._count("validation_status", status))
        }
        enrichment_statuses = {
            status: count
            for status in sorted(config.ENRICHMENT_STATUSES)
            if (count := self._count("enrichment_status", status))
        }
        ai_classifications = {
            classification: count
            for classification in sorted(config.AI_DEPENDENCY_LEVELS)
            if (
                count := self._count(
                    "ai_dependency_level", classification
                )
            )
        }
        return {
            "total_startups": self._count(),
            "validation_statuses": validation_statuses,
            "enrichment_statuses": enrichment_statuses,
            "ai_classifications": ai_classifications,
            "generated_at": datetime.now(UTC),
        }


# Backward-compatible import path. New code should import startup_service.
from scraper.api.services.startup_service import (  # noqa: E402
    StartupNotFoundError,
    StartupService,
    SupabaseConfigurationError,
)

SupabaseService = StartupService
