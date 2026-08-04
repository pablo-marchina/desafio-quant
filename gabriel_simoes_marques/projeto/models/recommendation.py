from pydantic import BaseModel
from enum import Enum


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Complexity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Recommendation(BaseModel):
    nvidia_tech: str                    # ex: "NVIDIA NIM", "TensorRT-LLM"
    technical_justification: str        # por que tecnicamente faz sentido
    business_justification: str         # impacto no negócio da startup
    priority: Priority
    complexity: Complexity
    next_action: str                    # próximo passo sugerido para o time NVIDIA
    evidence_used: list[str] = []       # URLs ou trechos que embasaram a recomendação
