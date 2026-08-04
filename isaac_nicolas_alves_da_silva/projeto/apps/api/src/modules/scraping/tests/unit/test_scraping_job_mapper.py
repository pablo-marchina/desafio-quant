"""Testes do mapper entre ScrapingJob e ScrapingJobModel."""

from uuid import uuid4

from apps.api.src.modules.scraping.domain.entities import ScrapingJob
from apps.api.src.modules.scraping.domain.enums import JobStatus
from apps.api.src.modules.scraping.infrastructure.database.mappers.scraping_job_mapper import (
    ScrapingJobMapper,
)
from apps.api.src.modules.scraping.infrastructure.database.models import (
    ScrapingJobModel,
)


def test_converts_entity_to_model() -> None:
    """Enum do domínio deve ser armazenado como string no model."""

    job = ScrapingJob(url="https://example.com")
    job.start()

    model = ScrapingJobMapper.to_model(job)

    assert model.id == job.id
    assert model.url == job.url
    assert model.status == "running"
    assert model.started_at == job.started_at


def test_converts_model_to_entity_with_external_result_id() -> None:
    """O result_id consultado separadamente deve voltar para a entidade."""

    original = ScrapingJob(url="https://example.com")
    model = ScrapingJobMapper.to_model(original)
    result_id = uuid4()

    entity = ScrapingJobMapper.to_entity(model, result_id=result_id)

    assert entity.id == original.id
    assert entity.status is JobStatus.PENDING
    assert entity.result_id == result_id


def test_updates_existing_model() -> None:
    """Atualização deve alterar o registro existente sem trocar seu objeto."""

    job = ScrapingJob(url="https://example.com")
    model = ScrapingJobModel(
        id=job.id,
        url=job.url,
        status=JobStatus.PENDING.value,
        error_message=None,
        created_at=job.created_at,
        started_at=None,
        finished_at=None,
    )

    job.start()
    ScrapingJobMapper.update_model(model, job)

    assert model.id == job.id
    assert model.status == "running"
    assert model.started_at == job.started_at
