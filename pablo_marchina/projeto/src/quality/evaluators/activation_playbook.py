from __future__ import annotations

from typing import Any

from src.quality.evaluators.base import BaseQualityEvaluator
from src.quantitative.params import CONFIDENCE_FLOAT_MAP
from src.services.product.activation_service import ActivationPlaybookService


class ActivationPlaybookEvaluator(BaseQualityEvaluator):
    def evaluate(self, analysis_run_id: str) -> dict[str, Any]:
        act_service = ActivationPlaybookService(self.session)
        recommendations = act_service.get_recommendations_for_run(analysis_run_id)
        playbook_present = len(recommendations) > 0

        evidence_support = 0.0
        top_confidence = "low"
        top_playbook_id: str | None = None
        top_playbook_name: str | None = None

        if playbook_present:
            top = act_service.get_top_for_run(analysis_run_id)
            if top:
                top_confidence = top.get("confidence", "low")
                top_playbook_id = top.get("playbook_id")
                top_playbook_name = top.get("playbook_name")
                evidence_support = CONFIDENCE_FLOAT_MAP.get(top_confidence, 0.3)

        return {
            "activation_playbook_present": playbook_present,
            "activation_playbook_evidence_support": evidence_support,
            "total_recommendations": len(recommendations),
            "top_confidence": top_confidence,
            "top_playbook_id": top_playbook_id,
            "top_playbook_name": top_playbook_name,
        }
