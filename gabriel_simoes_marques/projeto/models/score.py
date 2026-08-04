from pydantic import BaseModel


class DimensionScore(BaseModel):
    score: int           # 0-10
    rationale: str       # por que esse score


class StartupScore(BaseModel):
    startup_name: str
    technical_fit: DimensionScore
    ai_maturity: DimensionScore
    market_potential: DimensionScore
    strategic_value: DimensionScore
    urgency: DimensionScore
    total: int           # 0-100 (média ponderada)
    tier: str            # "S", "A", "B", "C"
    recommendation: str  # ação sugerida ao time NVIDIA
