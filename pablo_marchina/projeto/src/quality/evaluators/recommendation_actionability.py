from __future__ import annotations

from typing import Any

from src.quality.evaluators.base import BaseQualityEvaluator
from src.repositories.product import ProductRepository


class RecommendationActionabilityEvaluator(BaseQualityEvaluator):
    def evaluate(self, analysis_run_id: str) -> dict[str, Any]:
        repo = ProductRepository(self.session)
        run = repo.get_analysis_run(analysis_run_id)
        if run is None:
            return {
                "recommendation_actionability_score": 0.0,
                "has_recommended_motion": False,
                "has_next_step": False,
                "has_technical_experiment": False,
                "has_success_metrics": False,
            }

        output = run.output_snapshot_json or {}
        recommended_motion = output.get("recommended_motion") or ""
        has_motion = bool(recommended_motion)

        activation_recs = list(run.activation_recommendations or [])
        has_next_step = any(bool(r.next_step) for r in activation_recs)
        has_experiment = any(bool(r.technical_experiment) for r in activation_recs)
        has_metrics = any(bool(r.success_metrics_json) for r in activation_recs if hasattr(r, "success_metrics_json"))

        if not has_motion:
            return {
                "recommendation_actionability_score": 0.0,
                "has_recommended_motion": False,
                "has_next_step": False,
                "has_technical_experiment": False,
                "has_success_metrics": False,
            }

        score = 0.0
        if has_motion:
            score += 0.30
        if has_next_step:
            score += 0.30
        if has_experiment:
            score += 0.25
        if has_metrics:
            score += 0.15

        return {
            "recommendation_actionability_score": round(score, 4),
            "has_recommended_motion": has_motion,
            "has_next_step": has_next_step,
            "has_technical_experiment": has_experiment,
            "has_success_metrics": has_metrics,
        }
