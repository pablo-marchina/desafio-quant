from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import TypeAdapter
from dotenv import load_dotenv
from supabase import Client, create_client

from app.core.observability import LOGGER
from app.persistence.models import (
    AIAssessment,
    Evidence,
    EvidenceInput,
    ExecutiveBriefingRecord,
    ImpactEstimateRecord,
    InceptionFitAssessment,
    NVIDIARecommendation,
    PipelineRun,
    RecommendationCitation,
    RecommendationRefinementRecord,
    RunStatus,
    SearchQuery,
    Source,
    Startup,
)


FINAL_STATUSES = {"completed", "partial", "failed"}

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


class PersistenceError(RuntimeError):
    """Controlled error raised when a Supabase persistence operation fails."""


class PipelinePersistence:
    """Validates and persists pipeline entities using Supabase Data and Storage APIs."""

    def __init__(
        self,
        supabase_url: str | None = None,
        supabase_key: str | None = None,
        storage_bucket: str = "pipeline-traces",
        schema: str = "nvidia_inception",
        client: Client | Any | None = None,
    ) -> None:
        """Initialize a service-role Supabase client for the custom schema."""
        if client is None:
            if not supabase_url or not supabase_key:
                raise ValueError("SUPABASE_URL e uma chave secreta do backend são obrigatórios")
            client = create_client(supabase_url, supabase_key)
        self.supabase = client
        self.db = client.schema(schema)
        self.bucket = storage_bucket
        self.schema = schema

    @classmethod
    def from_env(cls) -> "PipelinePersistence":
        """Create the persistence service from backend-only environment variables."""
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        bucket = os.getenv("SUPABASE_TRACE_BUCKET", "pipeline-traces")
        return cls(supabase_url=url, supabase_key=key, storage_bucket=bucket)

    def save_startup(self, data: dict[str, Any]) -> UUID:
        """Return an existing startup UUID or insert a validated startup."""
        startup_id, _ = self.save_startup_with_status(data)
        return startup_id

    def save_startup_with_status(self, data: dict[str, Any]) -> tuple[UUID, bool]:
        """Persist a startup and report whether a new row was created."""
        try:
            startup = Startup.model_validate(data)
            existing = self._find_startup(startup)
            if existing:
                return UUID(existing["id"]), False

            payload = startup.model_dump(
                mode="json",
                exclude={"id", "created_at", "updated_at"},
                exclude_none=True,
            )
            response = self._table("startups").insert(payload).execute()
            row = self._require_first(response, "startups.insert")
            startup_id = UUID(row["id"])
            LOGGER.info("persistence_startup_saved", startup_id=str(startup_id), nome=startup.nome)
            return startup_id, True
        except PersistenceError:
            raise
        except Exception as exc:
            raise self._handle_error("save_startup_with_status", exc) from exc

    def create_pipeline_run(self, startup_id: UUID) -> UUID:
        """Create a running pipeline execution and return its UUID."""
        try:
            run = PipelineRun(
                startup_id=startup_id,
                status="running",
                started_at=datetime.now(UTC),
                current_stage="initialization",
            )
            payload = run.model_dump(
                mode="json",
                exclude={"id", "created_at", "updated_at"},
                exclude_none=True,
            )
            response = self._table("pipeline_runs").insert(payload).execute()
            row = self._require_first(response, "pipeline_runs.insert")
            run_id = UUID(row["id"])
            LOGGER.info("persistence_run_created", run_id=str(run_id), startup_id=str(startup_id))
            return run_id
        except PersistenceError:
            raise
        except Exception as exc:
            raise self._handle_error("create_pipeline_run", exc) from exc

    def update_stage(
        self,
        run_id: UUID,
        stage: str,
        status: RunStatus | str,
        extra_data: dict[str, Any] | None = None,
    ) -> None:
        """Update current stage and calculate final execution timing when applicable."""
        try:
            validated_status = TypeAdapter(RunStatus).validate_python(status)
            now = datetime.now(UTC)
            updates: dict[str, Any] = {
                "current_stage": stage,
                "status": validated_status,
            }
            allowed_extra = {
                "errors",
                "warnings",
                "source_errors",
                "trace_path",
                "duration_ms",
                "finished_at",
            }
            for key, value in (extra_data or {}).items():
                if key in allowed_extra:
                    updates[key] = value

            if validated_status in FINAL_STATUSES:
                updates.setdefault("finished_at", now.isoformat())
                updates.setdefault("duration_ms", self._calculate_duration_ms(run_id, now))

            self._table("pipeline_runs").update(_json_safe(updates)).eq("id", str(run_id)).execute()
            LOGGER.info(
                "persistence_stage_updated",
                run_id=str(run_id),
                stage=stage,
                status=validated_status,
            )
        except Exception as exc:
            raise self._handle_error("update_stage", exc, run_id=run_id) from exc

    def save_queries(self, run_id: UUID, queries: list[dict[str, Any]]) -> int:
        """Validate and upsert search queries for one execution."""
        if not queries:
            return 0
        try:
            models = [SearchQuery.model_validate({**query, "pipeline_run_id": run_id}) for query in queries]
            payload = [
                model.model_dump(mode="json", exclude={"id", "created_at"}, exclude_none=True)
                for model in models
            ]
            self._table("search_queries").upsert(
                payload,
                on_conflict="pipeline_run_id,consulta",
            ).execute()
            LOGGER.info("persistence_queries_saved", run_id=str(run_id), count=len(payload))
            return len(payload)
        except Exception as exc:
            raise self._handle_error("save_queries", exc, run_id=run_id) from exc

    def save_evidences(self, run_id: UUID, evidences: list[dict[str, Any]]) -> int:
        """Persist validated source/evidence pairs while preserving traceability."""
        saved = 0
        try:
            for raw in evidences:
                item = EvidenceInput.model_validate(raw)
                source = Source(
                    pipeline_run_id=run_id,
                    url=item.url,
                    tipo_fonte=item.tipo_fonte,
                    credibilidade=item.credibilidade,
                    status=item.source_status,
                )
                source_payload = source.model_dump(
                    mode="json",
                    exclude={"id", "created_at"},
                    exclude_none=True,
                )
                response = self._table("sources").upsert(
                    source_payload,
                    on_conflict="pipeline_run_id,url",
                ).execute()
                row = self._first(response) or self._find_source(run_id, str(item.url))
                if not row:
                    raise PersistenceError(f"sources.upsert não retornou id para {item.url}")

                evidence = Evidence(
                    pipeline_run_id=run_id,
                    source_id=UUID(row["id"]),
                    trecho=item.trecho,
                    score_confianca=item.score_confianca,
                    classificacao=item.classificacao,
                    contem_ia=item.contem_ia,
                    descartada=item.descartada,
                    motivo_descarte=item.motivo_descarte,
                )
                evidence_payload = evidence.model_dump(
                    mode="json",
                    exclude={"id", "created_at"},
                    exclude_none=True,
                )
                self._table("evidences").upsert(
                    evidence_payload,
                    on_conflict="pipeline_run_id,source_id,trecho",
                ).execute()
                saved += 1
            LOGGER.info("persistence_evidences_saved", run_id=str(run_id), count=saved)
            return saved
        except PersistenceError:
            raise
        except Exception as exc:
            raise self._handle_error("save_evidences", exc, run_id=run_id) from exc

    def save_assessment(self, run_id: UUID, assessment: dict[str, Any]) -> UUID:
        """Validate and upsert the unique AI maturity assessment of a run."""
        try:
            model = AIAssessment.model_validate({**assessment, "pipeline_run_id": run_id})
            payload = model.model_dump(
                mode="json",
                exclude={"id", "created_at"},
                exclude_none=True,
            )
            response = self._table("ai_assessments").upsert(
                payload,
                on_conflict="pipeline_run_id",
            ).execute()
            row = self._require_first(response, "ai_assessments.upsert")
            assessment_id = UUID(row["id"])
            LOGGER.info("persistence_assessment_saved", run_id=str(run_id), id=str(assessment_id))
            return assessment_id
        except PersistenceError:
            raise
        except Exception as exc:
            raise self._handle_error("save_assessment", exc, run_id=run_id) from exc

    def save_inception_fit(self, run_id: UUID, fit: dict[str, Any]) -> UUID:
        """Persist the Inception fit diagnosis separately from AI maturity."""
        try:
            model = InceptionFitAssessment(
                pipeline_run_id=run_id,
                eligibility_status=fit["eligibility_status"],
                startup_stage=fit["startup_stage"],
                fit_json=fit,
            )
            return self._upsert_run_artifact(
                "inception_fit_assessments",
                model.model_dump(mode="json", exclude={"id", "created_at"}),
                "inception_fit_assessments.upsert",
            )
        except PersistenceError:
            raise
        except Exception as exc:
            raise self._handle_error("save_inception_fit", exc, run_id=run_id) from exc

    def save_recommendation(
        self,
        run_id: UUID,
        recommendation: dict[str, Any],
        citations: list[dict[str, Any]],
    ) -> UUID:
        """Persist a recommendation and its structured document citations."""
        try:
            fit_scores = [
                float(item["fit_score"])
                for item in recommendation.get("recomendacoes", [])
                if item.get("fit_score") is not None
            ]
            model = NVIDIARecommendation(
                pipeline_run_id=run_id,
                recomendacao_json=recommendation,
                fit_score=max(fit_scores) if fit_scores else None,
            )
            payload = model.model_dump(
                mode="json",
                exclude={"id", "created_at"},
                exclude_none=True,
            )
            response = self._table("nvidia_recommendations").upsert(
                payload,
                on_conflict="pipeline_run_id",
            ).execute()
            row = self._require_first(response, "nvidia_recommendations.upsert")
            recommendation_id = UUID(row["id"])

            citation_models = [
                RecommendationCitation.model_validate(
                    {**citation, "recommendation_id": recommendation_id}
                )
                for citation in citations
            ]
            if citation_models:
                citation_payload = [
                    item.model_dump(
                        mode="json",
                        exclude={"id", "created_at"},
                        exclude_none=True,
                    )
                    for item in citation_models
                ]
                self._table("recommendation_citations").upsert(
                    citation_payload,
                    on_conflict="recommendation_id,tecnologia,url_doc,trecho_doc",
                ).execute()
            LOGGER.info(
                "persistence_recommendation_saved",
                run_id=str(run_id),
                recommendation_id=str(recommendation_id),
                citations=len(citation_models),
            )
            return recommendation_id
        except PersistenceError:
            raise
        except Exception as exc:
            raise self._handle_error("save_recommendation", exc, run_id=run_id) from exc

    def upload_trace(self, run_id: UUID, trace: dict[str, Any]) -> str:
        """Upload a UTF-8 JSON trace to private Storage and update its database path."""
        try:
            path = f"{run_id}.json"
            payload = json.dumps(trace, ensure_ascii=False, indent=2, default=str).encode("utf-8")
            self.supabase.storage.from_(self.bucket).upload(
                path=path,
                file=payload,
                file_options={
                    "content-type": "application/json; charset=utf-8",
                    "upsert": "true",
                },
            )
            self._table("pipeline_runs").update({"trace_path": path}).eq("id", str(run_id)).execute()
            LOGGER.info("persistence_trace_uploaded", run_id=str(run_id), path=path, bytes=len(payload))
            return path
        except Exception as exc:
            raise self._handle_error("upload_trace", exc, run_id=run_id) from exc

    def save_refinement(self, run_id: UUID, refinement: dict[str, Any]) -> UUID:
        """Persist the prioritized recommendation package for one execution."""
        try:
            content = refinement.get("recomendacao_refinada", {})
            model = RecommendationRefinementRecord(
                pipeline_run_id=run_id,
                refinement_json=refinement,
                fit_score=content.get("fit_score", 0.0),
            )
            return self._upsert_run_artifact(
                "recommendation_refinements",
                model.model_dump(mode="json", exclude={"id", "created_at"}),
                "recommendation_refinements.upsert",
            )
        except PersistenceError:
            raise
        except Exception as exc:
            raise self._handle_error("save_refinement", exc, run_id=run_id) from exc

    def save_impact_estimate(self, run_id: UUID, impact: dict[str, Any]) -> UUID:
        """Persist the grounded impact estimate for one execution."""
        try:
            model = ImpactEstimateRecord(
                pipeline_run_id=run_id,
                impact_json=impact,
                aggregate_index=impact.get("indice_impacto_agregado", 0),
            )
            return self._upsert_run_artifact(
                "impact_estimates",
                model.model_dump(mode="json", exclude={"id", "created_at"}),
                "impact_estimates.upsert",
            )
        except PersistenceError:
            raise
        except Exception as exc:
            raise self._handle_error("save_impact_estimate", exc, run_id=run_id) from exc

    def save_briefing(self, run_id: UUID, briefing: dict[str, Any]) -> UUID:
        """Persist the final executive Markdown for one execution."""
        try:
            model = ExecutiveBriefingRecord(
                pipeline_run_id=run_id,
                markdown=briefing["markdown"],
            )
            return self._upsert_run_artifact(
                "executive_briefings",
                model.model_dump(mode="json", exclude={"id", "created_at"}),
                "executive_briefings.upsert",
            )
        except PersistenceError:
            raise
        except Exception as exc:
            raise self._handle_error("save_briefing", exc, run_id=run_id) from exc

    def _upsert_run_artifact(
        self,
        table: str,
        payload: dict[str, Any],
        operation: str,
    ) -> UUID:
        response = self._table(table).upsert(payload, on_conflict="pipeline_run_id").execute()
        row = self._require_first(response, operation)
        return UUID(row["id"])

    def _table(self, name: str) -> Any:
        return self.db.table(name)

    def _find_startup(self, startup: Startup) -> dict[str, Any] | None:
        query = self._table("startups").select("id,nome,site_oficial")
        if startup.site_oficial:
            response = query.eq("site_oficial", str(startup.site_oficial)).limit(1).execute()
            existing = self._first(response)
            if existing:
                return existing
        response = (
            self._table("startups")
            .select("id,nome,site_oficial")
            .ilike("nome", startup.nome)
            .limit(1)
            .execute()
        )
        return self._first(response)

    def _find_source(self, run_id: UUID, url: str) -> dict[str, Any] | None:
        response = (
            self._table("sources")
            .select("id")
            .eq("pipeline_run_id", str(run_id))
            .eq("url", url)
            .limit(1)
            .execute()
        )
        return self._first(response)

    def _calculate_duration_ms(self, run_id: UUID, finished_at: datetime) -> int:
        response = self._table("pipeline_runs").select("started_at").eq("id", str(run_id)).limit(1).execute()
        row = self._first(response)
        if not row or not row.get("started_at"):
            return 0
        started_at = datetime.fromisoformat(str(row["started_at"]).replace("Z", "+00:00"))
        return max(0, int((finished_at - started_at).total_seconds() * 1000))

    @staticmethod
    def _first(response: Any) -> dict[str, Any] | None:
        data = getattr(response, "data", None)
        if isinstance(data, list):
            return data[0] if data else None
        return data if isinstance(data, dict) else None

    def _require_first(self, response: Any, operation: str) -> dict[str, Any]:
        row = self._first(response)
        if not row or not row.get("id"):
            raise PersistenceError(f"{operation} não retornou uma linha com id")
        return row

    def _handle_error(
        self,
        operation: str,
        error: Exception,
        run_id: UUID | None = None,
    ) -> PersistenceError:
        LOGGER.error(
            "persistence_operation_failed",
            operation=operation,
            run_id=str(run_id) if run_id else None,
            error=str(error),
        )
        return PersistenceError(f"{operation}: {error}")


def _json_safe(value: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(value, default=str))
