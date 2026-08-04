import json
import sys
from pathlib import Path


sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.schemas import (
    AIMaturityOutput,
    ExecutiveBriefingOutput,
    EvidenceValidationOutput,
    NVIDIARecommendationOutput,
    ImpactEstimationOutput,
    PipelineInput,
    PipelineOutput,
    ScraperOutput,
    SearchPlanOutput,
    RecommendationRefinementOutput,
)


SCHEMAS = {
    "pipeline_input": PipelineInput,
    "search_plan_output": SearchPlanOutput,
    "scraper_output": ScraperOutput,
    "evidence_validation_output": EvidenceValidationOutput,
    "ai_maturity_output": AIMaturityOutput,
    "nvidia_recommendation_output": NVIDIARecommendationOutput,
    "recommendation_refinement_output": RecommendationRefinementOutput,
    "impact_estimation_output": ImpactEstimationOutput,
    "executive_briefing_output": ExecutiveBriefingOutput,
    "pipeline_output": PipelineOutput,
}


if __name__ == "__main__":
    output_dir = Path(__file__).resolve().parents[2] / "docs" / "schemas"
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, model in SCHEMAS.items():
        path = output_dir / f"{name}.schema.json"
        path.write_text(
            json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(f"Exportados {len(SCHEMAS)} schemas para {output_dir}")
