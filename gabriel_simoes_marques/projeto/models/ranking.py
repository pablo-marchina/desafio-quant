from pydantic import BaseModel
from models.score import StartupScore


class RankedStartup(BaseModel):
    position: int
    startup_name: str
    score: StartupScore
    highlight: str       # 1 frase: por que está nessa posição
    action: str          # próximo passo concreto pro time NVIDIA


class RankingReport(BaseModel):
    ranked: list[RankedStartup]
    strategic_summary: str   # narrativa geral do portfólio
    top_pick: str            # startup mais recomendada pra Inception agora
    quick_wins: list[str]    # startups com alta urgência + bom score
    long_bets: list[str]     # startups com alto potencial mas early stage
