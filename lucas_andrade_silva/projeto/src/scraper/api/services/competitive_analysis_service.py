from __future__ import annotations

from typing import Any
from datetime import UTC, datetime

from scraper.api.services.job_manager import ProgressCallback


class CompetitiveAnalysisService:
    def __init__(self, startup_service: Any | None = None) -> None:
        self.startup_service = startup_service

    def analyze(
        self,
        startup: dict[str, Any],
        progress: ProgressCallback,
        *,
        question: str | None = None,
    ) -> dict[str, Any]:
        from agents.nvidia.graph import run_competitive_analysis

        company_name = str(startup.get("company_name") or "").strip()
        if not company_name:
            raise ValueError("Startup has no company_name")
        description = str(
            startup.get("company_description")
            or startup.get("description")
            or ""
        ).strip()
        if not description:
            raise ValueError("Startup has no documented service description")

        recommendation = startup.get("nvidia_recommendation") or {}
        if not isinstance(recommendation, dict):
            recommendation = {}
        stack = startup.get("tech_stack") or []
        if isinstance(stack, str):
            stack = [item.strip() for item in stack.split(",") if item.strip()]
        progress(10)
        result = run_competitive_analysis(
            {
                "empresa": company_name,
                "startup_url": startup.get("validated_url") or startup.get("website"),
                "cnae": startup.get("cnae"),
                "servico_startup_analisado": description,
                "stack_atual": list(stack),
                "pontos_fortes": [
                    {
                        "aspecto": "Serviço documentado",
                        "evidencia": description,
                        "fonte": startup.get("validated_url")
                        or startup.get("website")
                        or "Supabase",
                    }
                ],
                "gaps_identificados": recommendation.get("gaps", []),
                "recomendacoes_nvidia": recommendation.get("recommendations", []),
                "rag_answer": recommendation.get("final_answer")
                or recommendation.get("recommendation"),
                "github_discovery": startup.get("github_discovery") or {},
            },
            question or "comparar com big techs",
        )
        progress(95)
        analysis = {
            "startup_id": str(startup.get("candidate_id") or startup.get("id") or ""),
            "company_name": company_name,
            "competitive_report": result.get("competitive_report"),
            "briefing": result.get("briefing"),
            "final_answer": result.get("final_answer"),
            "structured_output": result.get("structured_output") or {},
            "generated_at": datetime.now(UTC).isoformat(),
        }
        if self.startup_service is not None:
            self.startup_service.update_startup(
                str(startup.get("id") or startup.get("candidate_id")),
                {"competitive_analysis": analysis},
            )
        return analysis
