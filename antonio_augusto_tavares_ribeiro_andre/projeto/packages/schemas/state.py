"""GraphState e estruturas de transporte do grafo (F0.5 / F2.1).

Estado compartilhado entre os nós do grafo LangGraph (ARQUITETURA §3): acumula da
consulta ao briefing. Aqui é o **contrato de dados** do estado; os *reducers* de
acumulação (ex.: `operator.add` em listas) e o checkpointer Postgres entram na
montagem do grafo (F2.1/F2.2).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from .aimi import AIMIScore
from .briefing import Briefing
from .enums import ExecutionMode, HITLMode, RunStatus
from .profile import StartupProfile
from .recommendation import Recommendation, ROIEstimate


class RawDocument(BaseModel):
    """Documento bruto coletado pelo scraper (F2.4), com proveniência mínima."""

    url: HttpUrl
    content: str
    fetched_at: datetime
    content_hash: str | None = None
    source_type: str | None = Field(
        default=None, description="firecrawl | playwright | trafilatura | bs4"
    )


class RetrievedChunk(BaseModel):
    """Trecho da KB NVIDIA recuperado pelo RAG híbrido + rerank (F3)."""

    text: str
    source_url: HttpUrl | None = None
    source_title: str | None = None
    score: float | None = Field(default=None, description="Score de relevância pós-rerank.")
    metadata: dict = Field(default_factory=dict)


class GraphState(BaseModel):
    """Estado do grafo multi-agente, da query ao briefing (ARQUITETURA §3)."""

    model_config = ConfigDict(extra="forbid")

    # Entrada / controle de run
    run_id: str
    query: str = Field(description="Consulta de entrada (nome/domínio ou setor/região).")
    mode: ExecutionMode = ExecutionMode.SINGLE_COMPANY
    hitl: HITLMode = HITLMode.SYNC
    status: RunStatus = RunStatus.PENDING

    # search_planner → scraper
    search_terms: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list, description="Fontes priorizadas (§9).")
    raw_docs: list[RawDocument] = Field(default_factory=list)

    # extractor / classifier
    profile: StartupProfile | None = None
    aimi: AIMIScore | None = None

    # nvidia_rag → recommender → gpu_benchmark
    retrieved: list[RetrievedChunk] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    benchmark: ROIEstimate | None = None

    # Saída
    briefing: Briefing | None = None

    # evidence_validator (F2.7) — retry limitado
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=2, ge=0)

    # human_review (F2.8) — modo auto (batch/cohort) marca p/ revisão assíncrona sem
    # bloquear a fila; o modo sync pausa via interrupt e não usa este campo.
    needs_review: bool = Field(
        default=False, description="HITL auto: run marcado p/ revisão humana (F2.8)."
    )

    # Reprodutibilidade / observabilidade
    prompt_version: str | None = Field(default=None, description="Versão de prompts (F0.12).")
    errors: list[str] = Field(default_factory=list)
    trace: dict = Field(
        default_factory=dict, description="Metadados de trace (tokens/custo/Langfuse)."
    )

    @property
    def can_retry(self) -> bool:
        """True se ainda há orçamento de retry de evidência (F2.7)."""
        return self.retry_count < self.max_retries
