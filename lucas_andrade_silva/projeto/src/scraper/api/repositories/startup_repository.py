from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from typing import Any, Protocol
from zoneinfo import ZoneInfo

import httpx


class RepositoryConfigurationError(RuntimeError):
    pass


class StartupRepository(Protocol):
    """Persistence contract consumed by the service layer."""

    def list(
        self,
        *,
        offset: int,
        limit: int,
        search: str | None = None,
        filters: dict[str, str | None] | None = None,
        present_filters: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], int]: ...

    def find_one(self, field: str, value: str) -> dict[str, Any] | None: ...

    def count(self, field: str | None = None, value: str | None = None) -> int: ...

    def count_present(self, field: str) -> int: ...

    def dashboard_summary_counts(self) -> dict[str, Any]: ...

    def ai_classification_counts(
        self, record_ids: set[str]
    ) -> dict[str, int]: ...

    def create(self, data: dict[str, Any]) -> dict[str, Any]: ...

    def update(self, record_id: str, data: dict[str, Any]) -> dict[str, Any] | None: ...

    def delete(self, record_id: str) -> bool: ...


class SupabaseStartupRepository:
    """CRUD repository using Supabase REST, with direct Postgres fallback."""

    _AUTOMATION_TIMEZONE = ZoneInfo("America/Bahia")
    _AUTOMATION_WEEKDAYS = {0, 3}
    _AI_CLASSIFICATIONS = {"AI_NATIVE", "AI_ENABLED", "NON_AI"}

    def __init__(self, table: str, timeout: float | None = None) -> None:
        self._validate_identifier(table)
        self.table = table
        self.timeout = timeout or float(os.getenv("API_SUPABASE_TIMEOUT", "15"))

    @staticmethod
    def _validate_identifier(value: str) -> None:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
            raise ValueError(f"Invalid database identifier: {value}")

    @staticmethod
    def _has_rest_credentials() -> bool:
        return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY"))

    @staticmethod
    def _headers(*, count: bool = False, representation: bool = False) -> dict[str, str]:
        key = os.getenv("SUPABASE_KEY")
        if not key:
            raise RepositoryConfigurationError("SUPABASE_KEY is not configured")
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        preferences = []
        if count:
            preferences.append("count=exact")
        if representation:
            preferences.append("return=representation")
        if preferences:
            headers["Prefer"] = ",".join(preferences)
        return headers

    def _rest_request(
        self,
        method: str,
        *,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
        count: bool = False,
        representation: bool = False,
    ) -> httpx.Response:
        base_url = os.getenv("SUPABASE_URL")
        if not base_url:
            raise RepositoryConfigurationError("SUPABASE_URL is not configured")
        response = httpx.request(
            method,
            f"{base_url.rstrip('/')}/rest/v1/{self.table}",
            params=params,
            json=payload,
            headers=self._headers(
                count=count, representation=representation
            ),
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response

    @staticmethod
    def _connection():
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RepositoryConfigurationError(
                "Configure SUPABASE_URL/SUPABASE_KEY or DATABASE_URL"
            )
        import psycopg2

        connection = psycopg2.connect(database_url)
        connection.set_session(readonly=False)
        return connection

    @staticmethod
    def _row(cursor, row) -> dict[str, Any]:
        columns = [column[0] for column in cursor.description]
        return dict(zip(columns, row))

    @staticmethod
    def _postgres_value(value: Any) -> Any:
        if isinstance(value, dict):
            from psycopg2.extras import Json

            return Json(value)
        return value

    @staticmethod
    def _parse_total(response: httpx.Response, fallback: int) -> int:
        content_range = response.headers.get("content-range", "")
        try:
            return int(content_range.rsplit("/", 1)[1])
        except (IndexError, ValueError):
            return fallback

    def list(
        self,
        *,
        offset: int,
        limit: int,
        search: str | None = None,
        filters: dict[str, str | None] | None = None,
        present_filters: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        active_filters = {
            field: value
            for field, value in (filters or {}).items()
            if value is not None
        }
        for field in active_filters:
            self._validate_identifier(field)
        for field in present_filters or []:
            self._validate_identifier(field)
        if self._has_rest_credentials():
            params: dict[str, Any] = {
                "select": "*",
                "order": "updated_at.desc.nullslast",
                "offset": str(offset),
                "limit": str(limit),
            }
            if search:
                params["company_name"] = f"ilike.*{search}*"
            for field, value in active_filters.items():
                params[field] = f"eq.{value}"
            for field in present_filters or []:
                params[field] = "not.is.null"
            response = self._rest_request(
                "GET", params=params, count=True
            )
            payload = response.json()
            rows = list(payload if isinstance(payload, list) else [])
            return rows, self._parse_total(response, len(rows))

        from psycopg2 import sql

        clauses = []
        values: list[Any] = []
        if search:
            clauses.append(sql.SQL("company_name ILIKE %s"))
            values.append(f"%{search}%")
        for field, value in active_filters.items():
            clauses.append(sql.SQL("{} = %s").format(sql.Identifier(field)))
            values.append(value)
        for field in present_filters or []:
            clauses.append(sql.SQL("{} IS NOT NULL").format(sql.Identifier(field)))
        where = (
            sql.SQL(" WHERE ") + sql.SQL(" AND ").join(clauses)
            if clauses
            else sql.SQL("")
        )
        table = sql.Identifier(self.table)
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL("SELECT COUNT(*) FROM {}").format(table) + where,
                    values,
                )
                total = int(cursor.fetchone()[0])
                cursor.execute(
                    sql.SQL("SELECT * FROM {}").format(table)
                    + where
                    + sql.SQL(
                        " ORDER BY updated_at DESC NULLS LAST LIMIT %s OFFSET %s"
                    ),
                    [*values, limit, offset],
                )
                rows = [
                    self._row(cursor, row) for row in cursor.fetchall()
                ]
        return rows, total

    def find_one(self, field: str, value: str) -> dict[str, Any] | None:
        self._validate_identifier(field)
        if self._has_rest_credentials():
            response = self._rest_request(
                "GET",
                params={"select": "*", field: f"eq.{value}", "limit": "1"},
            )
            payload = response.json()
            return dict(payload[0]) if isinstance(payload, list) and payload else None

        from psycopg2 import sql

        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL("SELECT * FROM {} WHERE {} = %s LIMIT 1").format(
                        sql.Identifier(self.table), sql.Identifier(field)
                    ),
                    (value,),
                )
                row = cursor.fetchone()
                return self._row(cursor, row) if row is not None else None

    def count(self, field: str | None = None, value: str | None = None) -> int:
        if field:
            self._validate_identifier(field)
        if self._has_rest_credentials():
            params: dict[str, Any] = {"select": "id", "limit": "1"}
            if field and value is not None:
                params[field] = f"eq.{value}"
            response = self._rest_request(
                "GET", params=params, count=True
            )
            return self._parse_total(response, 0)

        from psycopg2 import sql

        query = sql.SQL("SELECT COUNT(*) FROM {}").format(
            sql.Identifier(self.table)
        )
        params: tuple[Any, ...] = ()
        if field:
            query += sql.SQL(" WHERE {} = %s").format(sql.Identifier(field))
            params = (value,)
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                return int(cursor.fetchone()[0])

    def count_present(self, field: str) -> int:
        self._validate_identifier(field)
        if self._has_rest_credentials():
            response = self._rest_request(
                "GET",
                params={"select": "id", "limit": "1", field: "not.is.null"},
                count=True,
            )
            return self._parse_total(response, 0)

        from psycopg2 import sql

        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL(
                        "SELECT COUNT(*) FROM {} WHERE {} IS NOT NULL"
                    ).format(sql.Identifier(self.table), sql.Identifier(field))
                )
                return int(cursor.fetchone()[0])

    @staticmethod
    def _increment_count(counts: dict[str, int], value: Any) -> None:
        if value is None or value == "":
            return
        counts[str(value)] = counts.get(str(value), 0) + 1

    @classmethod
    def _increment_automation_registration(
        cls, counts: dict[str, int], value: Any
    ) -> None:
        if not value:
            return
        try:
            created_at = (
                value
                if isinstance(value, datetime)
                else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            )
        except (TypeError, ValueError):
            return
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        local_date = created_at.astimezone(cls._AUTOMATION_TIMEZONE).date()
        if local_date.weekday() not in cls._AUTOMATION_WEEKDAYS:
            return
        date_key = local_date.isoformat()
        counts[date_key] = counts.get(date_key, 0) + 1

    def dashboard_summary_counts(self) -> dict[str, Any]:
        validation_statuses: dict[str, int] = {}
        enrichment_statuses: dict[str, int] = {}
        ai_classifications: dict[str, int] = {}
        automation_registrations: dict[str, int] = {}
        candidate_ids: set[str] = set()
        recommendations_count = 0

        if self._has_rest_credentials():
            total = self.count()
            offset = 0
            page_size = 1000
            while offset < total:
                response = self._rest_request(
                    "GET",
                    params={
                        "select": (
                            "candidate_id,validation_status,enrichment_status,"
                            "ai_dependency_level,nvidia_recommendation,"
                            "created_at"
                        ),
                        "offset": str(offset),
                        "limit": str(page_size),
                    },
                )
                payload = response.json()
                rows = list(payload if isinstance(payload, list) else [])
                if not rows:
                    break
                for row in rows:
                    if row.get("candidate_id"):
                        candidate_ids.add(str(row["candidate_id"]))
                    self._increment_count(
                        validation_statuses, row.get("validation_status")
                    )
                    self._increment_count(
                        enrichment_statuses, row.get("enrichment_status")
                    )
                    self._increment_count(
                        ai_classifications, row.get("ai_dependency_level")
                    )
                    self._increment_automation_registration(
                        automation_registrations, row.get("created_at")
                    )
                    if row.get("nvidia_recommendation") is not None:
                        recommendations_count += 1
                offset += len(rows)
            return {
                "total_startups": total,
                "validation_statuses": validation_statuses,
                "enrichment_statuses": enrichment_statuses,
                "ai_classifications": ai_classifications,
                "recommendations_count": recommendations_count,
                "github_actions_registrations": [
                    {"date": date, "count": count}
                    for date, count in sorted(automation_registrations.items())
                ],
                "_candidate_ids": sorted(candidate_ids),
            }

        from psycopg2 import sql

        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL(
                        "SELECT candidate_id, validation_status, enrichment_status, "
                        "ai_dependency_level, nvidia_recommendation, "
                        "created_at FROM {}"
                    ).format(sql.Identifier(self.table))
                )
                rows = cursor.fetchall()
                for (
                    candidate_id,
                    validation_status,
                    enrichment_status,
                    ai_dependency_level,
                    nvidia_recommendation,
                    created_at,
                ) in rows:
                    if candidate_id:
                        candidate_ids.add(str(candidate_id))
                    self._increment_count(
                        validation_statuses, validation_status
                    )
                    self._increment_count(
                        enrichment_statuses, enrichment_status
                    )
                    self._increment_count(
                        ai_classifications, ai_dependency_level
                    )
                    self._increment_automation_registration(
                        automation_registrations, created_at
                    )
                    if nvidia_recommendation is not None:
                        recommendations_count += 1

        return {
            "total_startups": len(rows),
            "validation_statuses": validation_statuses,
            "enrichment_statuses": enrichment_statuses,
            "ai_classifications": ai_classifications,
            "recommendations_count": recommendations_count,
            "github_actions_registrations": [
                {"date": date, "count": count}
                for date, count in sorted(automation_registrations.items())
            ],
            "_candidate_ids": sorted(candidate_ids),
        }

    @classmethod
    def _business_ai_classification(cls, value: Any) -> str:
        normalized = str(value or "").strip().upper()
        if normalized == "AI_NATIVE":
            return "AI_NATIVE"
        if normalized in {"AI_ENABLED", "AI_MENTIONED"}:
            return "AI_ENABLED"
        return "NON_AI"

    def ai_classification_counts(
        self, record_ids: set[str]
    ) -> dict[str, int]:
        counts = {name: 0 for name in self._AI_CLASSIFICATIONS}
        if not record_ids:
            return counts

        if self._has_rest_credentials():
            ordered_ids = sorted(record_ids)
            chunk_size = 100
            for offset in range(0, len(ordered_ids), chunk_size):
                chunk = ordered_ids[offset : offset + chunk_size]
                response = self._rest_request(
                    "GET",
                    params={
                        "select": "id,ai_classification",
                        "id": f"in.({','.join(chunk)})",
                        "limit": str(chunk_size),
                    },
                )
                payload = response.json()
                rows = list(payload if isinstance(payload, list) else [])
                for row in rows:
                    classification = self._business_ai_classification(
                        row.get("ai_classification")
                    )
                    counts[classification] += 1
            return counts

        from psycopg2 import sql

        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL(
                        "SELECT ai_classification FROM {} "
                        "WHERE CAST(id AS TEXT) = ANY(%s)"
                    ).format(sql.Identifier(self.table)),
                    (list(record_ids),),
                )
                for (value,) in cursor.fetchall():
                    classification = self._business_ai_classification(value)
                    counts[classification] += 1
        return counts

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        if not data:
            raise ValueError("Create payload cannot be empty")
        for field in data:
            self._validate_identifier(field)
        if self._has_rest_credentials():
            response = self._rest_request(
                "POST", payload=data, representation=True
            )
            payload = response.json()
            if not isinstance(payload, list) or not payload:
                raise RuntimeError("Supabase did not return the created startup")
            return dict(payload[0])

        from psycopg2 import sql

        fields = list(data)
        query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING *").format(
            sql.Identifier(self.table),
            sql.SQL(", ").join(map(sql.Identifier, fields)),
            sql.SQL(", ").join(sql.Placeholder() for _ in fields),
        )
        with self._connection() as connection:
            with connection.cursor() as cursor:
                values = [
                    self._postgres_value(data[field]) for field in fields
                ]
                cursor.execute(query, values)
                return self._row(cursor, cursor.fetchone())

    def update(
        self, record_id: str, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        if not data:
            return self.find_one("id", record_id)
        payload = {
            **data,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        for field in payload:
            self._validate_identifier(field)
        if self._has_rest_credentials():
            response = self._rest_request(
                "PATCH",
                params={"id": f"eq.{record_id}"},
                payload=payload,
                representation=True,
            )
            result = response.json()
            return (
                dict(result[0])
                if isinstance(result, list) and result
                else None
            )

        from psycopg2 import sql

        fields = list(payload)
        assignments = sql.SQL(", ").join(
            sql.SQL("{} = {}").format(
                sql.Identifier(field), sql.Placeholder()
            )
            for field in fields
        )
        query = sql.SQL("UPDATE {} SET {} WHERE id = %s RETURNING *").format(
            sql.Identifier(self.table), assignments
        )
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    query,
                    [
                        self._postgres_value(payload[field])
                        for field in fields
                    ]
                    + [record_id],
                )
                row = cursor.fetchone()
                return self._row(cursor, row) if row is not None else None

    def delete(self, record_id: str) -> bool:
        if self._has_rest_credentials():
            response = self._rest_request(
                "DELETE",
                params={"id": f"eq.{record_id}"},
                representation=True,
            )
            payload = response.json()
            return bool(isinstance(payload, list) and payload)

        from psycopg2 import sql

        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL("DELETE FROM {} WHERE id = %s RETURNING id").format(
                        sql.Identifier(self.table)
                    ),
                    (record_id,),
                )
                return cursor.fetchone() is not None
