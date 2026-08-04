"""Entidades do dominio do modulo briefing."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from apps.api.src.modules.briefing.domain.exceptions import BriefingError


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Briefing:
    """Briefing executivo em Markdown gerado para uma startup."""

    startup_id: UUID
    content: str
    review_status: str = "pending"
    review_comment: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None

    id: UUID = field(default_factory=uuid4)
    generated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.content = self.content.strip()
        self.review_status = self.review_status.strip().lower()
        self.review_comment = self._normalize_optional_text(self.review_comment)
        self.reviewed_by = self._normalize_optional_text(self.reviewed_by)
        if not self.content:
            raise BriefingError("Briefing precisa ter conteudo.")
        if self.review_status not in {"pending", "approved", "rejected"}:
            raise BriefingError("review_status deve ser pending, approved ou rejected.")

    def update_content(self, content: str) -> None:
        """Substitui o conteudo (ex: prosa reescrita pelo Briefing Agent)."""

        content = content.strip()
        if not content:
            raise BriefingError("Briefing precisa ter conteudo.")
        self.content = content

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
            raise BriefingError("review_status deve ser pending, approved ou rejected.")
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
