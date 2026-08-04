"""Entidades do dominio do modulo recommendations."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from apps.api.src.modules.recommendations.domain.exceptions import (
    RecommendationError,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Recommendation:
    """Tecnologia NVIDIA recomendada para uma startup, com justificativa."""

    startup_id: UUID
    technology_slug: str
    technology_name: str
    category: str
    score: float
    justification: str
    matched_keywords: tuple[str, ...] = field(default_factory=tuple)
    evidence_ids: tuple[UUID, ...] = field(default_factory=tuple)
    confidence: float = 0.0
    complexity: str = "medium"
    signal_origins: tuple[str, ...] = field(default_factory=tuple)
    missing_signals: tuple[str, ...] = field(default_factory=tuple)
    nivel: str = "exploratoria"
    faltando: tuple[str, ...] = field(default_factory=tuple)
    review_status: str = "pending"
    review_comment: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None

    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.technology_slug = self.technology_slug.strip().lower()
        self.technology_name = self.technology_name.strip()
        self.category = self.category.strip()
        self.justification = self.justification.strip()
        self.complexity = self.complexity.strip().lower()
        self.review_status = self.review_status.strip().lower()
        self.review_comment = self._normalize_optional_text(self.review_comment)
        self.reviewed_by = self._normalize_optional_text(self.reviewed_by)

        if not self.technology_slug:
            raise RecommendationError("Recomendacao precisa ter technology_slug.")
        if not self.technology_name:
            raise RecommendationError("Recomendacao precisa ter technology_name.")
        if not self.justification:
            raise RecommendationError("Recomendacao precisa ter justificativa.")
        if not 0 <= self.score <= 1:
            raise RecommendationError("score deve ficar entre 0 e 1.")
        if not 0 <= self.confidence <= 1:
            raise RecommendationError("confidence deve ficar entre 0 e 1.")
        if self.complexity not in {"low", "medium", "high"}:
            raise RecommendationError("complexity deve ser low, medium ou high.")
        if self.nivel not in {"forte", "moderada", "exploratoria", "hipotese_prioritaria"}:
            raise RecommendationError(
                "nivel deve ser forte, moderada, exploratoria ou hipotese_prioritaria."
            )
        if self.review_status not in {"pending", "approved", "rejected"}:
            raise RecommendationError(
                "review_status deve ser pending, approved ou rejected."
            )

    def update_justification(self, text: str) -> None:
        """Substitui a justificativa (ex: revisao de linguagem via agente)."""

        text = text.strip()
        if not text:
            raise RecommendationError("Recomendacao precisa ter justificativa.")
        self.justification = text

    def review(
        self,
        *,
        status: str,
        comment: str | None = None,
        reviewed_by: str | None = None,
    ) -> None:
        """Registra uma revisao humana simples, sem auth completa."""

        status = status.strip().lower()
        if status not in {"pending", "approved", "rejected"}:
            raise RecommendationError(
                "review_status deve ser pending, approved ou rejected."
            )
        self.review_status = status
        self.review_comment = self._normalize_optional_text(comment)
        self.reviewed_by = self._normalize_optional_text(reviewed_by)
        self.reviewed_at = None if status == "pending" else utc_now()

    @staticmethod
    def _normalize_optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None
