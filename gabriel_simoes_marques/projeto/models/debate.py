from pydantic import BaseModel
from enum import Enum


class DebateRoundType(str, Enum):
    opening = "opening"
    attack = "attack"
    rebuttal = "rebuttal"


class BDIState(BaseModel):
    startup_name: str
    beliefs: dict          # fatos sobre A e B extraídos do grafo
    desires: str           # objetivo do agente
    intentions: list[str]  # argumentos planejados antes do debate


class DebateMove(BaseModel):
    agent: str             # nome da startup que o agente defende
    round_type: DebateRoundType
    argument: str          # argumento textual


class DebateVerdict(BaseModel):
    winner: str            # startup vencedora
    score_a: int           # 0-10
    score_b: int           # 0-10
    reasoning: str         # justificativa do juiz
    nvidia_recommendation: str  # qual integrar ao Inception e por quê


class DebateResult(BaseModel):
    startup_a: str
    startup_b: str
    model: str
    rounds: list[DebateMove]
    verdict: DebateVerdict
