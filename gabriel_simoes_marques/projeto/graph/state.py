from typing import TypedDict
from models.startup import Startup
from models.recommendation import Recommendation
from models.briefing import BriefingReport
from config.llm import DEFAULT_MODEL


class PipelineState(TypedDict):
    startup_name: str
    urls: list[str]
    model: str
    startup: Startup | None
    recommendations: list[Recommendation]
    briefing: BriefingReport | None
    error: str | None
