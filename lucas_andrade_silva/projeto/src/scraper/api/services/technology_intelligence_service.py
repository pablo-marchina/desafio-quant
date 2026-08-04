from __future__ import annotations

from typing import Any

from scraper.api.services.job_manager import ProgressCallback
from scraper.api.services.startup_service import StartupService
from scraper.market_intelligence import TechnologyIntelligenceAgent


class TechnologyIntelligenceService:
    def __init__(
        self,
        startup_service: StartupService,
        agent: TechnologyIntelligenceAgent | None = None,
    ) -> None:
        self.startup_service = startup_service
        self.agent = agent or TechnologyIntelligenceAgent()

    def analyze(
        self, startup: dict[str, Any], progress: ProgressCallback
    ) -> dict[str, Any]:
        report = self.agent.analyze(startup, progress)
        startup_id = str(startup.get("id") or startup.get("candidate_id") or "")
        if not startup_id:
            raise ValueError("Startup has no persistent identifier")
        self.startup_service.update_startup(
            startup_id, {"technology_intelligence": report}
        )
        return report
