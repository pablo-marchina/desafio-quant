"""Enums do modulo startups."""

from enum import Enum


class StartupEvidenceType(str, Enum):
    WEBSITE = "website"
    NEWS = "news"
    BLOG = "blog"
    DOCUMENTATION = "documentation"
    TECHNICAL = "technical"
    OTHER = "other"


class AiMaturityLevel(str, Enum):
    """Classificacao de maturidade de IA produzida pelo Startup Classifier Agent.

    Vocabulario INTERNO do modulo startups. O modulo agents tem o seu
    proprio enum equivalente (``StartupMaturityLevel``, em
    ``agents/domain/enums.py``), com os mesmos valores de string. A
    traducao e responsabilidade do adaptador
    (``startups/infrastructure/agent_adapters/agents_startup_classifier.py``).
    """

    AI_NATIVE = "ai_native"
    AI_ENABLED = "ai_enabled"
    NON_AI = "non_ai"


class AiWorkloadType(str, Enum):
    NLP = "nlp"
    VISION = "vision"
    RECOMMENDATION = "recommendation"
    SIMULATION = "simulation"
    ANALYTICS = "analytics"
    MLOPS = "mlops"
    SPEECH = "speech"
    UNKNOWN = "unknown"


class AiModelType(str, Enum):
    TRAINS_OWN = "trains_own"
    FINE_TUNING = "fine_tuning"
    API_BASED = "api_based"
    CLASSICAL_ML = "classical_ml"
    UNKNOWN = "unknown"


class AiDataModality(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    TABULAR = "tabular"
    THREE_D = "3d"
    LOG_NETWORK = "log_network"
    UNKNOWN = "unknown"


class AiDeploymentStage(str, Enum):
    RESEARCH = "research"
    MVP = "mvp"
    PILOT = "pilot"
    PRODUCTION = "production"
    SCALE = "scale"
    UNKNOWN = "unknown"


class AiInfraEnvironment(str, Enum):
    CLOUD = "cloud"
    ON_PREMISE = "on_premise"
    EDGE = "edge"
    HYBRID = "hybrid"
    UNKNOWN = "unknown"


class AiGpuNeed(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class AiLatencyRequirement(str, Enum):
    REALTIME = "realtime"
    BATCH = "batch"
    UNKNOWN = "unknown"


class FundingStage(str, Enum):
    """Estagio de funding publico da startup.

    Enum fechado (nao texto livre) porque sera preenchido pelo futuro
    Extraction Agent (LLM) — garante saida estruturada validavel em vez
    de variacoes livres tipo "Series A" vs "series-a" vs "A".
    """

    PRE_SEED = "pre_seed"
    SEED = "seed"
    SERIES_A = "series_a"
    SERIES_B = "series_b"
    SERIES_C_PLUS = "series_c_plus"
    UNKNOWN = "unknown"
