from __future__ import annotations

import re
from functools import partial
from typing import Any
from uuid import UUID

from langchain_core.runnables import Runnable, RunnableLambda

from app.persistence.persistence_service import PersistenceError, PipelinePersistence
from app.persistence.web_cache import SupabaseWebContentCache, set_web_pipeline_run_id
from app.services.enterprise_pipeline import EnterprisePipeline


class PipelinePersistenceHook:
    """Translate enterprise pipeline stage outputs into normalized database entities."""

    def __init__(self, persistence: PipelinePersistence) -> None:
        """Store the persistence service used by stage callbacks."""
        self.persistence = persistence

    def initialize(self, state: dict[str, Any]) -> None:
        """Persist startup and create the execution before the first agent runs."""
        pipeline_input = state["input"]
        startup_id = self.persistence.save_startup(
            {
                "external_id": pipeline_input.get("external_id"),
                "nome": pipeline_input["startup_name"],
                "site_oficial": pipeline_input.get("site_oficial"),
                "categoria": pipeline_input.get("categoria"),
                "cidade": pipeline_input.get("cidade"),
                "estado": pipeline_input.get("estado"),
                "pais": pipeline_input.get("pais") or "Brasil",
                "metadata": {
                    "descricao_curta": pipeline_input.get("descricao_curta"),
                    "contexto": pipeline_input.get("contexto"),
                },
            }
        )
        run_id = self.persistence.create_pipeline_run(startup_id)
        state["_persistence"] = {
            "startup_id": str(startup_id),
            "run_id": str(run_id),
        }
        set_web_pipeline_run_id(str(run_id))

    def stage_completed(
        self,
        state: dict[str, Any],
        stage: str,
        output: dict[str, Any],
    ) -> None:
        """Persist the normalized output of one successfully completed stage."""
        run_id = self._run_id(state)
        if run_id is None:
            return

        errors = []
        try:
            if stage == "search_planner":
                self.persistence.save_queries(
                    run_id,
                    [
                        {
                            "consulta": item["consulta"],
                            "camada": item.get("camada"),
                            "objetivo": item.get("objetivo"),
                            "resultados_count": 0,
                        }
                        for item in output.get("plano_consultas", [])
                    ],
                )
            elif stage == "scraper":
                self.persistence.save_queries(run_id, _queries_from_scraper(output))
            elif stage == "evidence_validator":
                self.persistence.save_evidences(run_id, _evidences_from_validator(output))
            elif stage == "ai_maturity_classifier":
                self.persistence.save_assessment(run_id, _assessment_from_classifier(output))
            elif stage == "inception_fit":
                self.persistence.save_inception_fit(run_id, output)
            elif stage == "nvidia_recommender_rag":
                self.persistence.save_recommendation(
                    run_id,
                    recommendation=output,
                    citations=_citations_from_recommendation(output),
                )
            elif stage == "recommendation_refiner":
                self.persistence.save_refinement(run_id, output)
            elif stage == "impact_estimator":
                self.persistence.save_impact_estimate(run_id, output)
            elif stage == "briefing_generator":
                self.persistence.save_briefing(run_id, output)
        except PersistenceError as exc:
            errors.append(str(exc))

        try:
            self.persistence.update_stage(run_id, stage, "running")
        except PersistenceError as exc:
            errors.append(str(exc))

        if errors:
            raise PersistenceError(" | ".join(errors))

    def stage_started(self, state: dict[str, Any], stage: str) -> None:
        """Expose the active stage before potentially slow network work begins."""
        run_id = self._run_id(state)
        if run_id is not None:
            self.persistence.update_stage(run_id, stage, "running")

    def finalize(self, state: dict[str, Any]) -> None:
        """Upload the trace and mark the execution completed, partial, or failed."""
        run_id = self._run_id(state)
        if run_id is None:
            return

        errors = []
        try:
            self.persistence.upload_trace(run_id, state.get("trace", {}))
        except PersistenceError as exc:
            errors.append(str(exc))

        critical_errors = state.get("critical_errors", state.get("errors", []))
        final_status = "partial" if critical_errors else "completed"
        if not state.get("classification_output"):
            final_status = "failed" if not state.get("scraper_output") else "partial"
        try:
            self.persistence.update_stage(
                run_id,
                "completed",
                final_status,
                extra_data={
                    "errors": critical_errors,
                    "warnings": state.get("warnings", []),
                    "source_errors": state.get("source_errors", []),
                },
            )
        except PersistenceError as exc:
            errors.append(str(exc))

        if errors:
            raise PersistenceError(" | ".join(errors))

    @staticmethod
    def _run_id(state: dict[str, Any]) -> UUID | None:
        value = state.get("_persistence", {}).get("run_id")
        return UUID(value) if value else None


def create_pipeline_with_persistence(
    persistence: PipelinePersistence,
    **pipeline_kwargs: Any,
) -> Runnable[dict[str, Any], dict[str, Any]]:
    """Create a LangChain runnable that persists all stages in degraded mode."""
    hook = PipelinePersistenceHook(persistence)
    pipeline_kwargs.setdefault("web_cache", SupabaseWebContentCache(persistence))
    pipeline = EnterprisePipeline(persistence_hook=hook, **pipeline_kwargs)
    return RunnableLambda(partial(_invoke_pipeline, pipeline=pipeline))


def run_pipeline_with_persistence(
    payload: dict[str, Any],
    persistence: PipelinePersistence | None = None,
    **pipeline_kwargs: Any,
) -> dict[str, Any]:
    """Run the persistent pipeline using an injected or environment client."""
    service = persistence or PipelinePersistence.from_env()
    return create_pipeline_with_persistence(service, **pipeline_kwargs).invoke(payload)


def _invoke_pipeline(
    payload: dict[str, Any],
    pipeline: EnterprisePipeline,
) -> dict[str, Any]:
    return pipeline.invoke(payload)


def _queries_from_scraper(output: dict[str, Any]) -> list[dict[str, Any]]:
    queries = []
    for task in output.get("resultados", []):
        consulta = task.get("consulta")
        if not consulta:
            continue
        queries.append(
            {
                "consulta": consulta,
                "camada": task.get("camada"),
                "objetivo": task.get("objetivo"),
                "resultados_count": len(task.get("resultados_busca", [])),
            }
        )
    return queries


def _evidences_from_validator(output: dict[str, Any]) -> list[dict[str, Any]]:
    evidences = []
    for key in ("evidencias_validadas", "evidencias_medias"):
        for item in output.get(key, []):
            evidences.append(
                {
                    "url": item["url"],
                    "tipo_fonte": item.get("tipo_fonte", "outro"),
                    "credibilidade": item.get("credibilidade_fonte", 0.0),
                    "source_status": "acessivel",
                    "trecho": item.get("trecho_evidencia") or None,
                    "score_confianca": item.get("score_confianca", 0.0),
                    "classificacao": item.get("classificacao", "baixa"),
                    "contem_ia": item.get("contem_evidencia_ia", False),
                    "descartada": False,
                }
            )
    for item in output.get("evidencias_descartadas", []):
        reason = item.get("motivo") or "evidência descartada"
        lower_reason = reason.lower()
        source_status = "quebrada" if "quebrada" in lower_reason or "404" in lower_reason else "acessivel"
        if "bloque" in lower_reason or "403" in lower_reason:
            source_status = "bloqueada"
        evidences.append(
            {
                "url": item["url"],
                "tipo_fonte": "outro",
                "credibilidade": 0.0,
                "source_status": source_status,
                "trecho": None,
                "score_confianca": 0.0,
                "classificacao": "baixa",
                "contem_ia": False,
                "descartada": True,
                "motivo_descarte": reason,
            }
        )
    return evidences


def _assessment_from_classifier(output: dict[str, Any]) -> dict[str, Any]:
    return {
        "classificacao": output["classificacao"],
        "nivel_maturidade": output["nivel_maturidade"],
        "confianca_classificacao": output["confianca_classificacao"],
        "tecnologias_utilizadas": output.get("tecnologias_utilizadas", {}),
        "necessidades": output.get("necessidades_limitacoes", []),
        "justificativa": output["justificativa"],
        "evidencias_usadas": output.get("evidencias_suporte", []),
    }


def _citations_from_recommendation(output: dict[str, Any]) -> list[dict[str, Any]]:
    citations = []
    recommendations = {
        item["tecnologia"]: item for item in output.get("recomendacoes", [])
    }
    for chunk in output.get("chunks_utilizados", []):
        metadata = chunk.get("metadata", {})
        technology = metadata.get("tecnologia")
        if technology not in recommendations:
            continue
        url = metadata.get("url_fonte")
        content = " ".join(str(chunk.get("content", "")).split())[:1200]
        if url and content:
            citations.append(
                {
                    "tecnologia": technology,
                    "trecho_doc": content,
                    "url_doc": url,
                }
            )

    if citations:
        return citations

    for technology, recommendation in recommendations.items():
        for citation in recommendation.get("citacoes", []):
            match = re.search(r"https?://[^\s]+", citation)
            if match:
                citations.append(
                    {
                        "tecnologia": technology,
                        "trecho_doc": citation[:1200],
                        "url_doc": match.group(0).rstrip(".,;:)"),
                    }
                )
    return citations
