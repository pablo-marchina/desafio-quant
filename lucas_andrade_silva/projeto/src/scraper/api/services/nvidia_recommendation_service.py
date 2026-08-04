from __future__ import annotations

from typing import Any

from scraper.api.services.job_manager import ProgressCallback


class NvidiaRecommendationService:
    """Backend-only adapter for the existing LangGraph/Qdrant workflow."""

    def __init__(self, startup_service: Any | None = None) -> None:
        self.startup_service = startup_service

    def recommend(
        self,
        startup: dict[str, Any],
        progress: ProgressCallback,
        *,
        need: str | None = None,
    ) -> dict[str, Any]:
        from agents.nvidia.graph import run_graph

        company_name = str(startup.get("company_name") or "").strip()
        if not company_name:
            raise ValueError("Startup has no company_name")
        documented_need = " ".join((need or "").split())
        description = str(
            startup.get("company_description")
            or startup.get("description")
            or ""
        ).strip()
        stack = list(startup.get("tech_stack") or [])
        source = str(
            startup.get("validated_url")
            or startup.get("website")
            or "Supabase"
        )
        points = (
            [
                {
                    "aspecto": "Serviço documentado",
                    "evidencia": description,
                    "fonte": source,
                }
            ]
            if description
            else []
        )
        progress(10)
        result = run_graph(
            (
                f"A startup {company_name} precisa {documented_need}. "
                "Recomende produtos e serviços NVIDIA para atender essa "
                "necessidade."
            ),
            output_mode="recommendation",
            competitive_context={
                "startup_context_preloaded": True,
                "startup_mencionada": True,
                "empresa": company_name,
                "dor_resolvida": description,
                "servico_startup_analisado": description,
                "stack_atual": stack,
                "pontos_fortes": points,
                "gaps_identificados": [],
                "dados_insuficientes": [],
                "user_documented_need": documented_need,
            },
        )
        if result.get("startup_lookup_status") == "erro":
            raise RuntimeError(
                str(result.get("final_answer") or "Falha no contexto da startup")
            )
        progress(95)
        recommendation = {
            "startup_id": str(
                startup.get("candidate_id") or startup.get("id") or ""
            ),
            "company_name": company_name,
            "recommendation": result.get("recommendation"),
            "recommendations": result.get("recomendacoes_nvidia", []),
            "gaps": result.get("gaps_identificados", []),
            "final_answer": result.get("final_answer"),
            "sources": result.get("sources", []),
            "roadmap": (result.get("structured_output") or {}).get("roadmap", []),
            "comparacao_bigtechs": (result.get("structured_output") or {}).get(
                "comparacao_bigtechs", []
            ),
            "structured_output": result.get("structured_output"),
        }
        if self.startup_service is not None:
            self.startup_service.update_startup(
                str(startup.get("id") or startup.get("candidate_id")),
                {"nvidia_recommendation": recommendation},
            )
        return recommendation
