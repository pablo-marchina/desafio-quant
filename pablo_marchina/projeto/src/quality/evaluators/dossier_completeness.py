from __future__ import annotations

from typing import Any

from src.database.models import ActivationDossierRecord
from src.quality.constants import DOSSIER_REQUIRED_SECTIONS
from src.quality.evaluators.base import BaseQualityEvaluator
from src.repositories.dossier import ActivationDossierRepository


class DossierCompletenessEvaluator(BaseQualityEvaluator):
    def evaluate(self, analysis_run_id: str) -> dict[str, Any]:
        dossier_repo = ActivationDossierRepository(self.session)
        dossier = dossier_repo.get_latest_for_analysis_run(analysis_run_id)
        if dossier is None:
            return {
                "dossier_exists": False,
                "dossier_section_completeness": 0.0,
                "missing_required_sections": list(DOSSIER_REQUIRED_SECTIONS),
            }
        sections_present = self._count_present_sections(dossier)
        total_required = len(DOSSIER_REQUIRED_SECTIONS)
        missing = DOSSIER_REQUIRED_SECTIONS - sections_present
        completeness = (total_required - len(missing)) / total_required
        return {
            "dossier_exists": True,
            "dossier_section_completeness": completeness,
            "missing_required_sections": sorted(missing),
            "dossier_id": dossier.id,
            "dossier_version": dossier.version,
        }

    def _count_present_sections(self, dossier: ActivationDossierRecord) -> set[str]:
        top = dossier.dossier_json
        present: set[str] = set()
        for section in DOSSIER_REQUIRED_SECTIONS:
            if section in top and top.get(section) is not None:
                val = top[section]
                if isinstance(val, dict) and len(val) > 0:
                    present.add(section)
                elif isinstance(val, list) and len(val) > 0:
                    present.add(section)
                elif isinstance(val, (str, bool, int, float)):
                    present.add(section)
        return present
