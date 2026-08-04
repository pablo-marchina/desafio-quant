"""Mapper entre ``ScrapingResult`` e ``ScrapingResultModel``."""

from apps.api.src.modules.scraping.domain.entities import ScrapingResult
from apps.api.src.modules.scraping.domain.enums import ScrapingMethod
from apps.api.src.modules.scraping.infrastructure.database.models import (
    ScrapingResultModel,
)


class ScrapingResultMapper:
    """Traduz resultados aprovados entre domínio e persistência."""

    @staticmethod
    def to_model(entity: ScrapingResult) -> ScrapingResultModel:
        """Converte a entidade em um novo model SQLAlchemy."""

        return ScrapingResultModel(
            id=entity.id,
            job_id=entity.job_id,
            url=entity.url,
            final_url=entity.final_url,
            title=entity.title,
            raw_html=entity.raw_html,
            raw_text=entity.raw_text,
            method=entity.method.value,
            status_code=entity.status_code,
            technical_score=entity.technical_score,
            text_score=entity.text_score,
            evidence_score=entity.evidence_score,
            quality_score=entity.quality_score,
            content_hash=entity.content_hash,
            metadata_=dict(entity.metadata),
            created_at=entity.created_at,
        )

    @staticmethod
    def to_entity(model: ScrapingResultModel) -> ScrapingResult:
        """Reconstrói a entidade a partir de um registro persistido."""

        return ScrapingResult(
            id=model.id,
            job_id=model.job_id,
            url=model.url,
            final_url=model.final_url,
            title=model.title,
            raw_html=model.raw_html,
            raw_text=model.raw_text,
            method=ScrapingMethod(model.method),
            status_code=model.status_code,
            technical_score=model.technical_score,
            text_score=model.text_score,
            evidence_score=model.evidence_score,
            quality_score=model.quality_score,
            content_hash=model.content_hash,
            metadata=dict(model.metadata_),
            created_at=model.created_at,
        )

    @staticmethod
    def update_model(
        model: ScrapingResultModel,
        entity: ScrapingResult,
    ) -> None:
        """Atualiza um model existente com os dados atuais da entidade."""

        model.job_id = entity.job_id
        model.url = entity.url
        model.final_url = entity.final_url
        model.title = entity.title
        model.raw_html = entity.raw_html
        model.raw_text = entity.raw_text
        model.method = entity.method.value
        model.status_code = entity.status_code
        model.technical_score = entity.technical_score
        model.text_score = entity.text_score
        model.evidence_score = entity.evidence_score
        model.quality_score = entity.quality_score
        model.content_hash = entity.content_hash
        model.metadata_ = dict(entity.metadata)
        model.created_at = entity.created_at
