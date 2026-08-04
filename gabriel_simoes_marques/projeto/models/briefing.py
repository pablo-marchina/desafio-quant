from pydantic import BaseModel
from datetime import datetime
from models.startup import Startup
from models.recommendation import Recommendation


class BriefingReport(BaseModel):
    startup: Startup
    recommendations: list[Recommendation] = []
    summary: str                            # parágrafo executivo gerado pelo Briefing Agent
    generated_at: datetime = datetime.now()
