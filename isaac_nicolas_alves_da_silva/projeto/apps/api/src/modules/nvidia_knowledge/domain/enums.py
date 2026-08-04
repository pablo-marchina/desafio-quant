"""Enums do modulo NVIDIA Knowledge."""

from enum import StrEnum


class NvidiaTechnologyCategory(StrEnum):
    """Categorias iniciais do catalogo NVIDIA."""

    MODEL_SERVING = "model_serving"
    MODEL_OPTIMIZATION = "model_optimization"
    MODEL_TRAINING = "model_training"
    DATA_SCIENCE = "data_science"
    SPEECH_AI = "speech_ai"
    ACCELERATED_COMPUTING = "accelerated_computing"
    AI_PLATFORM = "ai_platform"
    HEALTHCARE_AI = "healthcare_ai"
    STARTUP_PROGRAM = "startup_program"
    ROBOTICS_SIMULATION = "robotics_simulation"
    CYBERSECURITY = "cybersecurity"


class NvidiaKnowledgeSourcePriority(StrEnum):
    """Prioridade de ingestao das fontes NVIDIA."""

    P0 = "p0"
    P1 = "p1"
    P2 = "p2"


class NvidiaKnowledgeSourceType(StrEnum):
    """Tipo de fonte usada na base NVIDIA Knowledge."""

    OFFICIAL_DOCS = "official_docs"
    PRODUCT_PAGE = "product_page"
    DEVELOPER_PAGE = "developer_page"
    GITHUB_REPOSITORY = "github_repository"
    STRATEGIC_CONTEXT = "strategic_context"
