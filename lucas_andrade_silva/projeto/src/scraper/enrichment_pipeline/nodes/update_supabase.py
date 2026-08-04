"""Supabase read and update helpers for enrichment results."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from .. import config
from ..signals import confidence_bucket
from ..state import EnrichmentState


def _append_error(errors: object, source: str, message: str) -> object:
    if isinstance(errors, dict):
        merged = {key: list(value) if isinstance(value, list) else value for key, value in errors.items()}
        current = merged.get(source, [])
        if not isinstance(current, list):
            current = [str(current)]
        merged[source] = [*current, message]
        return merged
    return [*(errors or []), f"{source}: {message}"]


def _rest_headers() -> dict[str, str]:
    key = config.supabase_key()
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _has_rest_credentials() -> bool:
    return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY"))


def _has_database_url() -> bool:
    return bool(os.getenv("DATABASE_URL"))


def _database_url() -> str:
    value = os.getenv("DATABASE_URL")
    if not value:
        raise RuntimeError("Defina SUPABASE_URL/SUPABASE_KEY ou DATABASE_URL no .env")
    return value


def _pg_connect():
    import psycopg2

    connection = psycopg2.connect(_database_url())
    connection.set_session(readonly=False)
    return connection


def _pg_columns(connection, table: str = config.SUPABASE_TABLE) -> set[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            """,
            (table,),
        )
        return {row[0] for row in cursor.fetchall()}


def _table_url(table: str = config.SUPABASE_TABLE) -> str:
    return f"{config.supabase_url().rstrip('/')}/rest/v1/{table}"


def _request(
    method: str,
    *,
    params: dict[str, Any] | None = None,
    json: Any = None,
    extra_headers: dict[str, str] | None = None,
    table: str = config.SUPABASE_TABLE,
) -> httpx.Response:
    headers = _rest_headers()
    if extra_headers:
        headers.update(extra_headers)
    with httpx.Client(timeout=config.HTTP_TIMEOUT_SECONDS, follow_redirects=True) as client:
        response = client.request(method, _table_url(table), params=params, json=json, headers=headers)
    response.raise_for_status()
    return response


def ensure_results_schema() -> None:
    if not _has_database_url():
        return
    schema_path = Path(__file__).resolve().parents[1] / "schema.sql"
    with _pg_connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(schema_path.read_text(encoding="utf-8"))
            cursor.execute(
                """
                DO $$
                DECLARE
                    constraint_name TEXT;
                BEGIN
                    IF EXISTS (
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                          AND table_name = 'startup_ai_radar_catalog'
                    ) THEN
                        FOR constraint_name IN
                            SELECT tc.constraint_name
                            FROM information_schema.table_constraints AS tc
                            JOIN information_schema.check_constraints AS cc
                              ON cc.constraint_name = tc.constraint_name
                            WHERE tc.table_schema = 'public'
                              AND tc.table_name = 'startup_ai_radar_catalog'
                              AND tc.constraint_type = 'CHECK'
                              AND cc.check_clause ILIKE '%validation_status%'
                        LOOP
                            EXECUTE format(
                                'ALTER TABLE startup_ai_radar_catalog DROP CONSTRAINT %I',
                                constraint_name
                            );
                        END LOOP;
                    END IF;
                EXCEPTION WHEN undefined_table OR undefined_column THEN
                    NULL;
                END $$;
                """
            )


def _candidate_id(candidate: dict[str, Any]) -> str:
    return str(candidate.get("id") or candidate.get("raw_company_id") or candidate.get("normalized_name") or candidate.get("company_name"))


def _selected_source(state: EnrichmentState, source_type: str) -> dict[str, Any] | None:
    validated_url = str(state.get("validated_url") or "").strip()
    approved_threshold = config.IDENTITY_APPROVAL_THRESHOLD
    candidates = []
    for source in state.get("validated_sources", []):
        if str(source.get("source_type") or "") != source_type:
            continue
        validation = source.get("validation") or {}
        confidence = int(validation.get("confidence") or 0)
        classification = str(validation.get("classification") or "")
        if classification == "WRONG_COMPANY":
            continue
        if validated_url and str(source.get("url") or "").strip() == validated_url and confidence >= approved_threshold:
            candidates.append(source)
            continue
        if classification == "MATCH":
            candidates.append(source)
    candidates.sort(key=lambda item: int((item.get("validation") or {}).get("confidence") or 0), reverse=True)
    return candidates[0] if candidates else None


def build_result_payload(state: EnrichmentState) -> dict[str, Any]:
    candidate = state.get("candidate", {})
    cnpj_data = state.get("cnpj_data", {})
    classification = state.get("classification", {})
    website_source = _selected_source(state, "website") or _selected_source(state, "web_search")
    linkedin_source = _selected_source(state, "linkedin")
    github_profile = state.get("github_profile") or {}
    gupy_profile = state.get("gupy_profile") or {}
    identity_evidence = state.get("identity_evidence") or {}
    validated_urls = list(
        dict.fromkeys(
            state.get("validated_urls", [])
            or identity_evidence.get("validated_urls", [])
            or ([state.get("validated_url")] if state.get("validated_url") else [])
            or state.get("evidence_urls", [])
        )
    )
    candidate_urls = list(
        dict.fromkeys(
            state.get("candidate_urls", [])
            or identity_evidence.get("candidate_urls", [])
            or [attempt.get("url") for attempt in state.get("candidate_attempts", []) if attempt.get("url")]
            or [source.get("url") for source in state.get("source_candidates", []) if source.get("url")]
        )
    )
    rejected_urls = list(dict.fromkeys(state.get("rejected_urls", []) or identity_evidence.get("rejected_urls", []) or []))
    validated_url = str(state.get("validated_url") or (website_source or {}).get("url") or "") or None
    website = validated_url
    website_confidence = float((website_source or {}).get("validation", {}).get("confidence") or state.get("identity_confidence_score") or 0.0)
    company_description = (str(state.get("company_description") or "").strip() or None) if validated_url else None
    founding_year = cnpj_data.get("data_inicio_atividade") or candidate.get("foundation_year") or candidate.get("founding_year") or "Not specified"
    founding_year = str(founding_year)[:4] if str(founding_year).strip()[:4].isdigit() else str(founding_year or "Not specified")
    location = candidate.get("location") or candidate.get("city") or cnpj_data.get("municipio")
    if cnpj_data.get("uf"):
        location = ", ".join(part for part in (location, cnpj_data.get("uf")) if part)
    location = location or "Brazil"
    tech_signals = state.get("tech_signals", {})
    ai_dependency_level = str(
        classification.get("ai_dependency_level")
        or cnpj_data.get("classificacao_ia")
        or "INSUFFICIENT_EVIDENCE"
    )
    return {
        "candidate_id": _candidate_id(candidate),
        "company_name": candidate.get("company_name") or candidate.get("nome"),
        "website": website,
        "description": company_description,
        "github_tentativas": int(state.get("github_tentativas") or 0),
        "github_validacao_status": str(
            state.get("github_validacao_status") or "nao_executado"
        ),
        "technology_intelligence": (
            state.get("technology_intelligence") or None
        ),
        "ai_dependency_level": ai_dependency_level,
        "enrichment_status": state.get("enrichment_status") or "needs_review",
        "cnpj": cnpj_data.get("cnpj") or candidate.get("cnpj"),
        "cnpj_data": cnpj_data,
        "founding_year": founding_year,
        "location": location,
        "ai_technology_focus": (
            classification.get("ai_technology_focus")
            or cnpj_data.get("justificativa_ia")
            or "Unknown"
        ),
        "target_market": (
            classification.get("target_market")
            or cnpj_data.get("setor_inferido")
        ),
        "key_milestones": classification.get("key_milestones"),
        "socios": cnpj_data.get("socios") or [],
        "cnae": cnpj_data.get("cnae"),
        "source_url": validated_url or candidate.get("source_url"),
        "validation_status": classification.get("validation_status"),
        "is_active": state.get("is_active", True),
        "updated_at": datetime.now(UTC).isoformat(),
    }


def _fetch_existing_result(candidate_id: str) -> dict[str, Any] | None:
    if _has_rest_credentials() and not _has_database_url():
        response = _request(
            "GET",
            params={"select": "*", "candidate_id": f"eq.{candidate_id}", "limit": "1"},
            table=config.ENRICHMENT_RESULTS_TABLE,
        )
        payload = response.json()
        return dict(payload[0]) if isinstance(payload, list) and payload else None
    with _pg_connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT * FROM {config.ENRICHMENT_RESULTS_TABLE} WHERE candidate_id = %s", (candidate_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            columns = [item[0] for item in cursor.description]
            return dict(zip(columns, row))


def _fetch_existing_result_by_company_name(company_name: str) -> dict[str, Any] | None:
    normalized = company_name.strip()
    if not normalized:
        return None
    if _has_rest_credentials() and not _has_database_url():
        response = _request(
            "GET",
            params={"select": "*", "company_name": f"eq.{normalized}", "limit": "1"},
            table=config.ENRICHMENT_RESULTS_TABLE,
        )
        payload = response.json()
        return dict(payload[0]) if isinstance(payload, list) and payload else None
    with _pg_connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT * FROM {config.ENRICHMENT_RESULTS_TABLE} WHERE LOWER(company_name) = LOWER(%s) ORDER BY updated_at DESC NULLS LAST LIMIT 1",
                (normalized,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            columns = [item[0] for item in cursor.description]
            return dict(zip(columns, row))


def _prefer_stronger(existing: dict[str, Any] | None, incoming: dict[str, Any]) -> dict[str, Any]:
    current = dict(existing or {})
    merged = dict(current)
    incoming_confidence = float(incoming.get("identity_confidence_score") or incoming.get("website_confidence") or 0.0)
    existing_confidence = float(current.get("identity_confidence_score") or current.get("website_confidence") or 0.0)
    strong_fields = {
        "validated_url",
        "website",
        "description",
        "company_description",
        "github_org",
        "linkedin_url",
        "crunchbase_url",
        "gupy_url",
    }
    for key, value in incoming.items():
        if key not in strong_fields:
            if value not in (None, "", [], {}):
                merged[key] = value
            elif key not in merged:
                merged[key] = value
            continue
        if value in (None, "", [], {}):
            continue
        if not current.get(key) or incoming_confidence >= max(existing_confidence, config.IDENTITY_APPROVAL_THRESHOLD):
            merged[key] = value
            merged["website_confidence"] = incoming.get("website_confidence") or merged.get("website_confidence")
    if current.get("website") and existing_confidence > incoming_confidence:
        merged["website"] = current["website"]
        merged["website_confidence"] = current.get("website_confidence")
    if current.get("company_description") and existing_confidence > incoming_confidence:
        merged["company_description"] = current["company_description"]
        merged["description"] = current.get("description") or current["company_description"]
    if not merged.get("website") and incoming.get("website_candidate"):
        merged["website_candidate"] = incoming["website_candidate"]
    return merged


def save_enrichment_result(state: EnrichmentState) -> None:
    payload = build_result_payload(state)
    candidate_id = str(payload["candidate_id"])
    existing = _fetch_existing_result(candidate_id)
    if existing is None:
        existing = _fetch_existing_result_by_company_name(str(payload.get("company_name") or ""))
    payload = _prefer_stronger(existing, payload)
    existing_row_id = str((existing or {}).get("id") or "").strip()
    existing_candidate_id = str((existing or {}).get("candidate_id") or "").strip()
    updating_legacy_row = bool(existing_row_id and existing_candidate_id and existing_candidate_id != candidate_id)
    if _has_rest_credentials() and not _has_database_url():
        if updating_legacy_row:
            _request(
                "PATCH",
                params={"id": f"eq.{existing_row_id}"},
                json=payload,
                extra_headers={"Prefer": "return=minimal"},
                table=config.ENRICHMENT_RESULTS_TABLE,
            )
        else:
            _request(
                "POST",
                params={"on_conflict": "candidate_id"},
                json=payload,
                extra_headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
                table=config.ENRICHMENT_RESULTS_TABLE,
            )
        return

    ensure_results_schema()
    try:
        from psycopg2.extras import Json
    except ModuleNotFoundError:
        Json = None

    with _pg_connect() as connection:
        columns = _pg_columns(connection, config.ENRICHMENT_RESULTS_TABLE)
        filtered_payload = {key: value for key, value in payload.items() if key in columns}
        fields = list(filtered_payload)
        placeholders = ", ".join(["%s"] * len(fields))
        assignments = ", ".join(
            f"{field} = EXCLUDED.{field}"
            for field in fields
            if field not in {"candidate_id", "created_at"}
        )
        values = [
            Json(value) if Json is not None and isinstance(value, (dict, list)) else value
            for value in (filtered_payload[field] for field in fields)
        ]
        with connection.cursor() as cursor:
            if updating_legacy_row:
                update_fields = [field for field in fields if field not in {"id", "created_at"}]
                update_assignments = ", ".join(f"{field} = %s" for field in update_fields)
                update_values = [
                    Json(filtered_payload[field]) if Json is not None and isinstance(filtered_payload[field], (dict, list)) else filtered_payload[field]
                    for field in update_fields
                ]
                cursor.execute(
                    f"UPDATE {config.ENRICHMENT_RESULTS_TABLE} SET {update_assignments} WHERE id = %s",
                    [*update_values, existing_row_id],
                )
            else:
                cursor.execute(
                    f"""
                    INSERT INTO {config.ENRICHMENT_RESULTS_TABLE} ({', '.join(fields)})
                    VALUES ({placeholders})
                    ON CONFLICT (candidate_id) DO UPDATE SET {assignments}
                    """,
                    values,
                )


def save_github_validation_result(state: EnrichmentState) -> bool:
    if state.get("github_validacao_status") != "confirmado" or not state.get("github_repo_validado"):
        return False
    candidate = state.get("candidate", {})
    empresa_id = _candidate_id(candidate)
    payload = {
        "empresa_id": empresa_id,
        "github_repo_url": state.get("github_repo_validado"),
        "criterios_atendidos": list(state.get("github_validacao_criterios") or []),
        "evidencia": state.get("github_validacao_evidencia"),
        "data_validacao": datetime.now(UTC).isoformat(),
    }
    if _has_rest_credentials() and not _has_database_url():
        _request(
            "POST",
            params={"on_conflict": "empresa_id,github_repo_url"},
            json=payload,
            extra_headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
            table=config.GITHUB_VALIDATIONS_TABLE,
        )
        return True

    ensure_results_schema()
    try:
        from psycopg2.extras import Json
    except ModuleNotFoundError:
        Json = None
    with _pg_connect() as connection:
        columns = _pg_columns(connection, config.GITHUB_VALIDATIONS_TABLE)
        filtered_payload = {key: value for key, value in payload.items() if key in columns}
        fields = list(filtered_payload)
        values = [
            Json(value) if Json is not None and isinstance(value, (dict, list)) else value
            for value in (filtered_payload[field] for field in fields)
        ]
        placeholders = ", ".join(["%s"] * len(fields))
        assignments = ", ".join(
            f"{field} = EXCLUDED.{field}"
            for field in fields
            if field not in {"empresa_id", "github_repo_url", "created_at"}
        )
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {config.GITHUB_VALIDATIONS_TABLE} ({', '.join(fields)})
                VALUES ({placeholders})
                ON CONFLICT (empresa_id, github_repo_url) DO UPDATE SET {assignments}
                """,
                values,
            )
    return True


def should_save_enrichment_result(state: EnrichmentState) -> tuple[bool, str | None]:
    candidate = state.get("candidate", {})
    if not candidate.get("id") and not candidate.get("raw_company_id"):
        return False, "candidato sem id"
    if (state.get("cnpj_data") or {}).get("cnpj"):
        return True, None
    if state.get("validated_sources"):
        return True, None
    if state.get("discard_reason"):
        return True, None
    identity_evidence = state.get("identity_evidence") or {}
    if identity_evidence.get("sources"):
        return True, None
    if state.get("rejected_urls"):
        return True, None
    return False, "sem evidencias de identidade"


def update_supabase_node(state: EnrichmentState) -> dict[str, Any]:
    candidate = state.get("candidate", {})
    if state.get("dry_run"):
        return {"updated": False}
    candidate_id = candidate.get("id")
    if not candidate_id:
        return {"updated": False, "errors": _append_error(state.get("errors", {}), "update_supabase", "candidato sem id")}
    should_save, skip_reason = should_save_enrichment_result(state)
    if not should_save:
        return {"updated": False, "save_skipped_reason": skip_reason}
    payload_preview = build_result_payload(state)
    try:
        ensure_results_schema()
        save_enrichment_result(state)
        github_validation_saved = save_github_validation_result(state)
        return {
            "updated": True,
            "update_payload_preview": {
                "candidate_id": payload_preview.get("candidate_id"),
                "company_name": payload_preview.get("company_name"),
                "validated_url": payload_preview.get("validated_url"),
                "website_candidate": payload_preview.get("website_candidate"),
                "website_confidence": payload_preview.get("website_confidence"),
                "identity_confidence_score": payload_preview.get("identity_confidence_score"),
                "validated_urls_count": len(payload_preview.get("validated_urls") or []),
                "candidate_urls_count": len(payload_preview.get("candidate_urls") or []),
                "rejected_urls_count": len(payload_preview.get("rejected_urls") or []),
                "github_repo_validado": state.get("github_repo_validado"),
                "github_validation_saved": github_validation_saved,
            },
        }
    except Exception as error:
        return {
            "updated": False,
            "update_payload_preview": {
                "candidate_id": payload_preview.get("candidate_id"),
                "company_name": payload_preview.get("company_name"),
                "validated_url": payload_preview.get("validated_url"),
                "website_candidate": payload_preview.get("website_candidate"),
                "website_confidence": payload_preview.get("website_confidence"),
                "identity_confidence_score": payload_preview.get("identity_confidence_score"),
            },
            "errors": _append_error(state.get("errors", {}), "update_supabase", str(error)),
        }


def load_candidates(limit: int | None = None, company_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    if not _has_rest_credentials():
        try:
            import psycopg2.extras as psycopg2_extras
            cursor_factory = psycopg2_extras.RealDictCursor
        except ModuleNotFoundError:
            cursor_factory = None

        clauses: list[str] = []
        params: list[Any] = []
        with _pg_connect() as connection:
            if company_id:
                clauses.append("id = %s")
                params.append(company_id)
            elif status:
                clauses.append("validation_status = %s")
                params.append(status)
            else:
                clauses.append("validation_status IN ('APPROVED', 'REVIEW')")
            where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
            limit_sql = " LIMIT %s" if limit is not None else ""
            if limit is not None:
                params.append(limit)
            with connection.cursor(cursor_factory=cursor_factory) as cursor:
                cursor.execute(
                    f"SELECT * FROM {config.SUPABASE_TABLE}{where} ORDER BY updated_at DESC NULLS LAST{limit_sql}",
                    params,
                )
                return [dict(row) for row in cursor.fetchall()]

    params: dict[str, Any] = {"select": "*"}
    headers = {}
    if company_id:
        params["id"] = f"eq.{company_id}"
    elif status:
        params["validation_status"] = f"eq.{status}"
    else:
        params["validation_status"] = "in.(APPROVED,REVIEW)"
    if limit is not None:
        params["limit"] = str(limit)
    else:
        headers["Range"] = "0-999"
    response = _request("GET", params=params, extra_headers=headers)
    payload = response.json()
    return list(payload if isinstance(payload, list) else [])
