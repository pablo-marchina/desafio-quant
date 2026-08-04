from __future__ import annotations

import os
import sqlite3
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypedDict
from uuid import uuid4

import requests
from langchain_core.runnables import Runnable
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

from app.chains.agent_chains import (
    create_briefing_generator_chain,
    create_classifier_chain,
    create_evidence_validator_chain,
    create_impact_estimator_chain,
    create_inception_fit_chain,
    create_recommendation_refiner_chain,
    create_recommender_chain,
    create_scraper_chain,
    create_search_planner_chain,
)
from app.agents.briefing_generator_agent import BriefingGeneratorAgent
from app.agents.impact_estimator_agent import ImpactEstimatorAgent
from app.agents.inception_fit_agent import InceptionFitAgent
from app.agents.recommendation_agent import RecommendationAgent
from app.core.cache import JsonFileCache
from app.core.contracts import validate_contract
from app.core.observability import LOGGER
from app.core.retry import execute_with_retry
from app.core.schemas import PipelineInput, PipelineOutput, StageTrace
from app.rag.recommender import NVIDIARecommenderRAG


STAGE_CACHE_VERSIONS = {
    "nvidia_recommender_rag": "v2",
}


class EnterprisePipelineState(TypedDict, total=False):
    request: dict[str, Any]
    input: dict[str, Any]
    trace: dict[str, Any]
    errors: list[Any]
    warnings: list[str]
    source_errors: list[Any]
    critical_errors: list[Any]
    investigation_attempt: int
    search_plan: dict[str, Any]
    scraper_output: dict[str, Any]
    validation_output: dict[str, Any]
    classification_output: dict[str, Any]
    inception_fit_output: dict[str, Any]
    recommendation_output: dict[str, Any]
    refinement_output: dict[str, Any]
    impact_output: dict[str, Any]
    briefing_output: dict[str, Any]
    final_output: dict[str, Any]


class EnterprisePipeline:
    def __init__(
        self,
        session: requests.Session | None = None,
        recommender: NVIDIARecommenderRAG | None = None,
        cache: JsonFileCache | None = None,
        use_cache: bool = True,
        delay_seconds: float = 2.0,
        verificar_urls: bool = True,
        retry_wait_multiplier: float = 2.0,
        search_client: Any | None = None,
        firecrawl_client: Any | None = None,
        trafilatura_extractor: Any | None = None,
        persistence_hook: Any | None = None,
        recommendation_agent: RecommendationAgent | None = None,
        impact_estimator_agent: ImpactEstimatorAgent | None = None,
        briefing_generator_agent: BriefingGeneratorAgent | None = None,
        inception_fit_agent: InceptionFitAgent | None = None,
        web_cache: Any | None = None,
    ) -> None:
        self.cache = cache or JsonFileCache()
        self.use_cache = use_cache
        self.retry_wait_multiplier = retry_wait_multiplier
        self.persistence_hook = persistence_hook
        self.search_chain = create_search_planner_chain(enable_retry=False)
        self.scraper_chain = create_scraper_chain(
            session=session,
            delay_seconds=delay_seconds,
            search_client=search_client,
            firecrawl_client=firecrawl_client,
            trafilatura_extractor=trafilatura_extractor,
            enable_retry=False,
            web_cache=web_cache,
        )
        self.validator_chain = create_evidence_validator_chain(
            session=session,
            verificar_urls=verificar_urls,
            enable_retry=False,
        )
        self.classifier_chain = create_classifier_chain(enable_retry=False)
        self.inception_fit_chain = create_inception_fit_chain(
            agent=inception_fit_agent,
            enable_retry=False,
        )
        rag_recommender = recommender or NVIDIARecommenderRAG()
        shared_store = getattr(rag_recommender, "store", None)
        self.recommender_chain = create_recommender_chain(
            recommender=rag_recommender,
            enable_retry=False,
        )
        self.recommendation_refiner_chain = create_recommendation_refiner_chain(
            agent=recommendation_agent or RecommendationAgent(store=shared_store),
            enable_retry=False,
        )
        self.impact_estimator_chain = create_impact_estimator_chain(
            agent=impact_estimator_agent or ImpactEstimatorAgent(store=shared_store),
            enable_retry=False,
        )
        self.briefing_generator_chain = create_briefing_generator_chain(
            agent=briefing_generator_agent,
            enable_retry=False,
        )
        self.checkpointer = self._create_checkpointer()
        self.runnable = self._build_runnable()

    def invoke(self, payload: PipelineInput | dict[str, Any]) -> dict[str, Any]:
        raw = (
            payload.model_dump(mode="json")
            if isinstance(payload, PipelineInput)
            else dict(payload)
        )
        thread_id = str(raw.pop("thread_id", None) or uuid4())
        result = self.runnable.invoke(
            {"request": raw},
            config={"configurable": {"thread_id": thread_id}, "recursion_limit": 30},
        )
        return result["final_output"]

    def _build_runnable(self) -> Runnable[dict[str, Any], dict[str, Any]]:
        graph = StateGraph(EnterprisePipelineState)
        retry = RetryPolicy(max_attempts=3, initial_interval=0.5, backoff_factor=2.0)
        graph.add_node("initialize", self._initialize)
        graph.add_node("search_planner", self._search_stage, retry_policy=retry)
        graph.add_node("scraper", self._scraper_stage, retry_policy=retry)
        graph.add_node("evidence_validator", self._validator_stage, retry_policy=retry)
        graph.add_node("research_feedback", self._research_feedback)
        graph.add_node("ai_maturity_classifier", self._classifier_stage)
        graph.add_node("inception_fit", self._inception_fit_stage)
        graph.add_node("nvidia_recommender_rag", self._recommender_stage, retry_policy=retry)
        graph.add_node("recommendation_refiner", self._recommendation_refiner_stage)
        graph.add_node("impact_estimator", self._impact_estimator_stage)
        graph.add_node("briefing_generator", self._briefing_generator_stage)
        graph.add_node("finalize", self._finalize)

        graph.add_edge(START, "initialize")
        graph.add_edge("initialize", "search_planner")
        graph.add_edge("search_planner", "scraper")
        graph.add_edge("scraper", "evidence_validator")
        graph.add_conditional_edges(
            "evidence_validator",
            self._route_after_validation,
            {"retry_research": "research_feedback", "classify": "ai_maturity_classifier"},
        )
        graph.add_edge("research_feedback", "search_planner")
        graph.add_edge("ai_maturity_classifier", "inception_fit")
        graph.add_edge("inception_fit", "nvidia_recommender_rag")
        graph.add_edge("nvidia_recommender_rag", "recommendation_refiner")
        graph.add_edge("recommendation_refiner", "impact_estimator")
        graph.add_edge("impact_estimator", "briefing_generator")
        graph.add_edge("briefing_generator", "finalize")
        graph.add_edge("finalize", END)
        return graph.compile(checkpointer=self.checkpointer)

    @staticmethod
    def _create_checkpointer() -> SqliteSaver:
        checkpoint_path = Path(
            os.getenv(
                "LANGGRAPH_CHECKPOINT_PATH",
                Path(__file__).resolve().parents[2]
                / "data"
                / "cache"
                / "langgraph"
                / "checkpoints.sqlite",
            )
        )
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(checkpoint_path, check_same_thread=False)
        return SqliteSaver(connection)

    @staticmethod
    def _route_after_validation(state: dict[str, Any]) -> str:
        validation = state.get("validation_output") or {}
        evidence_count = len(validation.get("evidencias_validadas") or []) + len(
            validation.get("evidencias_medias") or []
        )
        scraper = state.get("scraper_output") or {}
        has_collected_data = bool(
            scraper.get("resultados_buscas") or scraper.get("paginas_completas")
        )
        attempts = int(state.get("investigation_attempt", 0))
        if evidence_count == 0 and has_collected_data and attempts < 1:
            return "retry_research"
        return "classify"

    @staticmethod
    def _research_feedback(state: dict[str, Any]) -> dict[str, Any]:
        attempt = int(state.get("investigation_attempt", 0)) + 1
        input_payload = dict(state["input"])
        context = str(input_payload.get("contexto") or "").strip()
        input_payload["contexto"] = (
            context
            + " Busca complementar: priorize site oficial, documentação técnica, vagas de ML e fontes independentes corroboradas."
        ).strip()
        state["input"] = input_payload
        state["investigation_attempt"] = attempt
        state["warnings"].append(
            "LangGraph acionou investigação complementar por ausência de evidência qualificada."
        )
        for key in ("search_plan", "scraper_output", "validation_output"):
            state.pop(key, None)
        return state

    def _initialize(self, state: EnterprisePipelineState) -> dict[str, Any]:
        pipeline_input = validate_contract(PipelineInput, state.get("request", {}))
        state = {
            "input": pipeline_input.model_dump(mode="json"),
            "trace": {},
            "errors": [],
            "warnings": [],
            "source_errors": [],
            "critical_errors": [],
            "investigation_attempt": 0,
        }
        if self.persistence_hook is not None:
            try:
                self.persistence_hook.initialize(state)
            except Exception as exc:
                self._record_persistence_error(state, "initialization", exc)
        return state

    def _search_stage(self, state: dict[str, Any]) -> dict[str, Any]:
        return self._execute_stage(
            state,
            stage="search_planner",
            input_payload=state["input"],
            output_key="search_plan",
            operation=lambda: self.search_chain.invoke(state["input"]),
        )

    def _scraper_stage(self, state: dict[str, Any]) -> dict[str, Any]:
        return self._execute_dependent_stage(
            state,
            stage="scraper",
            dependency="search_plan",
            output_key="scraper_output",
            input_builder=lambda: state["search_plan"],
            operation=lambda payload: self.scraper_chain.invoke(payload),
        )

    def _validator_stage(self, state: dict[str, Any]) -> dict[str, Any]:
        return self._execute_dependent_stage(
            state,
            stage="evidence_validator",
            dependency="scraper_output",
            output_key="validation_output",
            input_builder=lambda: {
                "site_oficial": state["input"].get("site_oficial"),
                "dados_brutos": state["scraper_output"],
            },
            operation=lambda payload: self.validator_chain.invoke(payload),
        )

    def _classifier_stage(self, state: dict[str, Any]) -> dict[str, Any]:
        return self._execute_dependent_stage(
            state,
            stage="ai_maturity_classifier",
            dependency="validation_output",
            output_key="classification_output",
            input_builder=lambda: {"validacao": state["validation_output"]},
            operation=lambda payload: self.classifier_chain.invoke(payload),
        )

    def _recommender_stage(self, state: dict[str, Any]) -> dict[str, Any]:
        return self._execute_dependent_stage(
            state,
            stage="nvidia_recommender_rag",
            dependency="classification_output",
            output_key="recommendation_output",
            input_builder=lambda: {"classificacao_ia": state["classification_output"]},
            operation=lambda payload: self.recommender_chain.invoke(payload),
        )

    def _inception_fit_stage(self, state: dict[str, Any]) -> dict[str, Any]:
        return self._execute_dependent_stage(
            state,
            stage="inception_fit",
            dependency="classification_output",
            output_key="inception_fit_output",
            input_builder=lambda: {
                "startup_profile": state["input"],
                "classificacao_ia": state["classification_output"],
                "validacao_evidencias": state.get("validation_output"),
            },
            operation=lambda payload: self.inception_fit_chain.invoke(payload),
        )

    def _recommendation_refiner_stage(self, state: dict[str, Any]) -> dict[str, Any]:
        return self._execute_dependent_stage(
            state,
            stage="recommendation_refiner",
            dependency="recommendation_output",
            output_key="refinement_output",
            input_builder=lambda: {
                "classificacao_ia": state["classification_output"],
                "recomendacao_rag": state["recommendation_output"],
                "startup_profile": state["input"],
                "evidencias_altas": state.get("validation_output", {}).get(
                    "evidencias_validadas", []
                ),
            },
            operation=lambda payload: self.recommendation_refiner_chain.invoke(payload),
        )

    def _impact_estimator_stage(self, state: dict[str, Any]) -> dict[str, Any]:
        return self._execute_dependent_stage(
            state,
            stage="impact_estimator",
            dependency="refinement_output",
            output_key="impact_output",
            input_builder=lambda: {
                "classificacao_ia": state["classification_output"],
                "recomendacao_refinada": state["refinement_output"],
                "dados_adicionais": state["input"].get("dados_adicionais", {}),
            },
            operation=lambda payload: self.impact_estimator_chain.invoke(payload),
        )

    def _briefing_generator_stage(self, state: dict[str, Any]) -> dict[str, Any]:
        return self._execute_dependent_stage(
            state,
            stage="briefing_generator",
            dependency="impact_output",
            output_key="briefing_output",
            input_builder=lambda: {
                "startup_profile": state["input"],
                "classificacao_ia": state["classification_output"],
                "recomendacao_refinada": state["refinement_output"],
                "estimativa_impacto": state["impact_output"],
                "validacao_evidencias": state.get("validation_output"),
                "inception_fit": state.get("inception_fit_output"),
            },
            operation=lambda payload: self.briefing_generator_chain.invoke(payload),
        )

    def _execute_dependent_stage(
        self,
        state: dict[str, Any],
        stage: str,
        dependency: str,
        output_key: str,
        input_builder: Callable[[], dict[str, Any]],
        operation: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> dict[str, Any]:
        if dependency not in state:
            message = f"Etapa {stage} não executada porque {dependency} está ausente"
            self._record_critical_error(state, message)
            state["trace"][stage] = StageTrace(
                status="falha",
                duration_ms=0,
                attempts=0,
                error=message,
            ).model_dump(mode="json")
            return state
        input_payload = input_builder()
        return self._execute_stage(
            state,
            stage=stage,
            input_payload=input_payload,
            output_key=output_key,
            operation=lambda: operation(input_payload),
        )

    def _execute_stage(
        self,
        state: dict[str, Any],
        stage: str,
        input_payload: dict[str, Any],
        output_key: str,
        operation: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        started = time.perf_counter()
        self._notify_persistence_stage_started(state, stage)
        cache_version = STAGE_CACHE_VERSIONS.get(stage, "v1")
        cache_key = self.cache.key_for(f"{cache_version}_{stage}", input_payload)
        if self.use_cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                state[output_key] = cached
                warnings, critical_issue = self._record_output_diagnostics(state, stage, cached)
                state["trace"][stage] = StageTrace(
                    status="cache",
                    duration_ms=round((time.perf_counter() - started) * 1000, 2),
                    attempts=0,
                    output=cached,
                    warnings=warnings,
                ).model_dump(mode="json")
                LOGGER.info("stage_cache_hit", stage=stage, startup=state["input"]["startup_name"])
                self._notify_persistence_stage(state, stage, cached)
                return state

        try:
            output, attempts = execute_with_retry(
                operation,
                stage=stage,
                retryable=(Exception,),
                max_attempts=3,
                wait_multiplier=self.retry_wait_multiplier,
            )
            if self.use_cache:
                self.cache.set(cache_key, output)
            duration = round((time.perf_counter() - started) * 1000, 2)
            state[output_key] = output
            warnings, critical_issue = self._record_output_diagnostics(state, stage, output)
            state["trace"][stage] = StageTrace(
                status="parcial" if critical_issue else "completo",
                duration_ms=duration,
                attempts=attempts,
                tokens_consumidos=_tokens_from_output(output),
                output=output,
                warnings=warnings,
            ).model_dump(mode="json")
            LOGGER.info(
                "pipeline_stage_completed",
                stage=stage,
                duration_ms=duration,
                attempts=attempts,
                result_count=_result_count(output),
                tokens_consumidos=_tokens_from_output(output),
            )
            self._notify_persistence_stage(state, stage, output)
        except Exception as exc:
            duration = round((time.perf_counter() - started) * 1000, 2)
            message = f"{stage}: {exc}"
            self._record_critical_error(state, message)
            state["trace"][stage] = StageTrace(
                status="falha",
                duration_ms=duration,
                attempts=3,
                error=str(exc),
            ).model_dump(mode="json")
            LOGGER.error("pipeline_stage_failed", stage=stage, duration_ms=duration, error=str(exc))
        return state

    def _notify_persistence_stage_started(
        self,
        state: dict[str, Any],
        stage: str,
    ) -> None:
        if self.persistence_hook is None:
            return
        try:
            self.persistence_hook.stage_started(state, stage)
        except Exception as exc:
            self._record_persistence_error(state, f"{stage}:start", exc)

    def _finalize(self, state: dict[str, Any]) -> dict[str, Any]:
        if self.persistence_hook is not None:
            try:
                self.persistence_hook.finalize(state)
            except Exception as exc:
                self._record_persistence_error(state, "finalization", exc)
        classification = state.get("classification_output") or {}
        recommendation = state.get("recommendation_output")
        refinement = state.get("refinement_output")
        impact = state.get("impact_output")
        briefing = state.get("briefing_output") or {}
        critical_errors = state["critical_errors"]
        mandatory_complete = bool(classification and briefing.get("markdown"))
        final_status = "completo"
        if critical_errors:
            final_status = "parcial" if mandatory_complete else "falha"
        output = {
            "startup": state["input"]["startup_name"],
            "status": final_status,
            "classificacao": classification.get("classificacao"),
            "nivel_maturidade": classification.get("nivel_maturidade"),
            "inception_fit": state.get("inception_fit_output"),
            "recomendacao": recommendation,
            "recomendacao_refinada": refinement,
            "impacto_estimado": impact,
            "briefing_markdown": briefing.get("markdown"),
            "pipeline_run_id": state.get("_persistence", {}).get("run_id"),
            "trace": state["trace"],
            "errors": critical_errors,
            "warnings": state["warnings"],
            "source_errors": state["source_errors"],
            "critical_errors": critical_errors,
        }
        validated = validate_contract(PipelineOutput, output).model_dump(mode="json")
        return {"final_output": validated}

    def _notify_persistence_stage(
        self,
        state: dict[str, Any],
        stage: str,
        output: dict[str, Any],
    ) -> None:
        if self.persistence_hook is None:
            return
        try:
            self.persistence_hook.stage_completed(state, stage, output)
        except Exception as exc:
            self._record_persistence_error(state, stage, exc)

    @staticmethod
    def _record_persistence_error(
        state: dict[str, Any],
        stage: str,
        error: Exception,
    ) -> None:
        message = f"persistence:{stage}: {error}"
        EnterprisePipeline._record_critical_error(state, message)
        LOGGER.error("pipeline_persistence_degraded", stage=stage, error=str(error))

    @staticmethod
    def _record_critical_error(state: dict[str, Any], message: str) -> None:
        state["critical_errors"].append(message)
        state["errors"] = state["critical_errors"]

    def _record_output_diagnostics(
        self,
        state: dict[str, Any],
        stage: str,
        output: dict[str, Any],
    ) -> tuple[list[str], str | None]:
        warnings = [f"{stage}: {error}" for error in _embedded_errors(output)]
        state["warnings"].extend(warnings)
        if stage in {"scraper", "evidence_validator"}:
            state["source_errors"].extend(warnings)
        critical_issue = _critical_output_issue(stage, output, state)
        if critical_issue:
            self._record_critical_error(state, critical_issue)
        return warnings, critical_issue


def create_pipeline(**kwargs: Any) -> Runnable[dict[str, Any], dict[str, Any]]:
    return EnterprisePipeline(**kwargs).runnable


def run_enterprise_pipeline(
    payload: PipelineInput | dict[str, Any],
    **kwargs: Any,
) -> dict[str, Any]:
    return EnterprisePipeline(**kwargs).invoke(payload)


def _result_count(output: dict[str, Any]) -> int:
    for key in (
        "recomendacoes",
        "estimativas_impacto",
        "evidencias_validadas",
        "resultados_buscas",
        "plano_consultas",
    ):
        value = output.get(key)
        if isinstance(value, list):
            return len(value)
    return 1


def _tokens_from_output(output: dict[str, Any]) -> int:
    usage = output.get("usage_metadata") or output.get("token_usage") or {}
    return int(usage.get("total_tokens") or usage.get("total") or 0)


def _embedded_errors(output: dict[str, Any]) -> list[str]:
    errors = output.get("erros") or output.get("erros_validacao") or output.get("errors") or []
    normalized = []
    for error in errors:
        if isinstance(error, dict):
            normalized.append(str(error.get("erro") or error.get("mensagem") or error))
        else:
            normalized.append(str(error))
    if output.get("status") == "falha" and not normalized:
        normalized.append("etapa retornou status falha")
    return normalized


def _critical_output_issue(
    stage: str,
    output: dict[str, Any],
    state: dict[str, Any],
) -> str | None:
    if output.get("status") == "falha":
        return f"{stage}: etapa retornou status falha"
    if stage == "scraper":
        results = output.get("resultados_buscas") or []
        pages = output.get("paginas_completas") or []
        if not results and not pages:
            return "scraper: nenhuma fonte utilizavel foi coletada"
    if stage == "evidence_validator":
        evidence = (output.get("evidencias_validadas") or []) + (
            output.get("evidencias_medias") or []
        )
        if not evidence:
            return "evidence_validator: nenhuma evidencia utilizavel foi validada"
    classification = (state.get("classification_output") or {}).get("classificacao")
    if classification and classification != "Non-AI":
        if stage == "nvidia_recommender_rag" and not output.get("recomendacoes"):
            return "nvidia_recommender_rag: nenhuma recomendacao fundamentada para startup com IA"
        if stage == "impact_estimator" and not output.get("estimativas_impacto"):
            return "impact_estimator: nenhuma estimativa foi produzida para startup com IA"
    return None
