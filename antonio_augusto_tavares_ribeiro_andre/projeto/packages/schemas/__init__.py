"""Contratos Pydantic v2 compartilhados (F0.5).

Toda afirmação carrega proveniência (ver `Evidence`/`Claim`). Modelos por domínio:
- evidência:        `Evidence`, `Claim`
- perfil (§2):      `StartupProfile` (+ `Founder`, `Funding`, `Product`, `Customer`, `Technology`)
- maturidade:       `AIMIScore`, `PillarScore`
- recomendação:     `Recommendation`, `ROIEstimate`
- briefing:         `Briefing`
- estado do grafo:  `GraphState` (+ `RawDocument`, `RetrievedChunk`)
- enums:            classes/faixas/modos/status

Verificação rápida (DoD F0): `python -c "from packages.schemas import StartupProfile"`.
"""

from .aimi import MAX_SCORE_WITHOUT_EVIDENCE, AIMIScore, PillarScore, band_for
from .briefing import Briefing
from .enums import (
    AIMIBand,
    AIMIPillar,
    BriefingStatus,
    Classification,
    Complexity,
    ExecutionMode,
    HITLMode,
    Priority,
    RunStatus,
)
from .evidence import Claim, Evidence
from .profile import (
    Customer,
    Founder,
    Funding,
    Product,
    StartupProfile,
    Technology,
)
from .recommendation import Recommendation, ROIEstimate
from .state import GraphState, RawDocument, RetrievedChunk
from .tech_vocab import normalize_tech, normalize_techs, tech_matches

__all__ = [
    # evidência
    "Evidence",
    "Claim",
    # perfil
    "StartupProfile",
    "Founder",
    "Funding",
    "Product",
    "Customer",
    "Technology",
    # maturidade
    "AIMIScore",
    "PillarScore",
    "band_for",
    "MAX_SCORE_WITHOUT_EVIDENCE",
    # recomendação
    "Recommendation",
    "ROIEstimate",
    # vocabulário de tech (facetas F5.11)
    "normalize_tech",
    "normalize_techs",
    "tech_matches",
    # briefing
    "Briefing",
    # estado do grafo
    "GraphState",
    "RawDocument",
    "RetrievedChunk",
    # enums
    "Classification",
    "AIMIPillar",
    "AIMIBand",
    "Priority",
    "Complexity",
    "ExecutionMode",
    "HITLMode",
    "RunStatus",
    "BriefingStatus",
]
