from pydantic import BaseModel
from enum import Enum


class AIClassification(str, Enum):
    AI_NATIVE = "AI-native"
    AI_ENABLED = "AI-enabled"
    NON_AI = "non-AI"


class Evidence(BaseModel):
    content: str
    source_url: str | None = None
    source_type: str | None = None


class Startup(BaseModel):
    name: str
    website: str | None = None
    logo_url: str | None = None
    sector: str | None = None
    description: str | None = None
    founding_year: int | None = None
    hq_location: str | None = None
    employee_count: int | None = None
    founders: list[str] = []
    funding_usd: float | None = None
    funding_stage: str | None = None        # "Seed", "Series A", "Series B", etc.
    investors: list[str] = []
    tech_stack: list[str] = []
    products: list[str] = []               # produtos / soluções principais
    use_cases: list[str] = []              # casos de uso concretos
    business_model: str | None = None     # "B2B SaaS", "API", "Marketplace", etc.
    target_market: str | None = None      # segmento de clientes alvo
    github_url: str | None = None
    linkedin_url: str | None = None
    classification: AIClassification | None = None
    evidence: list[Evidence] = []
    raw_text: str | None = None
