"""Testes do mapper entre ScrapingResult e ScrapingResultModel."""

from hashlib import sha256
from uuid import uuid4

from apps.api.src.modules.scraping.domain.entities import ScrapingResult
from apps.api.src.modules.scraping.domain.enums import ScrapingMethod
from apps.api.src.modules.scraping.infrastructure.database.mappers.scraping_result_mapper import (
    ScrapingResultMapper,
)


def make_result() -> ScrapingResult:
    """Cria um resultado completo reutilizado pelos testes."""

    text = "Conteúdo aprovado sobre inteligência artificial."

    return ScrapingResult(
        job_id=uuid4(),
        url="https://example.com",
        final_url="https://example.com/about",
        title="Startup",
        raw_html=f"<html>{text}</html>",
        raw_text=text,
        method=ScrapingMethod.BEAUTIFULSOUP,
        status_code=200,
        technical_score=1.0,
        text_score=0.90,
        evidence_score=0.80,
        quality_score=0.89,
        content_hash=sha256(text.encode("utf-8")).hexdigest(),
        metadata={"response_bytes": 100},
    )


def test_converts_result_entity_to_model() -> None:
    """Campos do domínio devem ser preparados para persistência."""

    result = make_result()

    model = ScrapingResultMapper.to_model(result)

    assert model.id == result.id
    assert model.method == "beautifulsoup"
    assert model.metadata_ == {"response_bytes": 100}
    assert model.content_hash == result.content_hash


def test_restores_result_entity_from_model() -> None:
    """Model persistido deve reconstruir a entidade equivalente."""

    original = make_result()

    restored = ScrapingResultMapper.to_entity(
        ScrapingResultMapper.to_model(original)
    )

    assert restored.id == original.id
    assert restored.method is ScrapingMethod.BEAUTIFULSOUP
    assert restored.metadata == original.metadata
    assert restored.quality_score == original.quality_score


def test_updates_existing_result_model() -> None:
    """Alterações da entidade devem atualizar o model existente."""

    result = make_result()
    model = ScrapingResultMapper.to_model(result)

    result.title = "Título atualizado"
    result.metadata["word_count"] = 120
    ScrapingResultMapper.update_model(model, result)

    assert model.title == "Título atualizado"
    assert model.metadata_ == {
        "response_bytes": 100,
        "word_count": 120,
    }
