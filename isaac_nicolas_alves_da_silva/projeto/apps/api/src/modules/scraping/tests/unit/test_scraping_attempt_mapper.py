"""Testes do mapper entre ScrapingAttempt e ScrapingAttemptModel."""

from uuid import uuid4

from apps.api.src.modules.scraping.domain.entities import ScrapingAttempt
from apps.api.src.modules.scraping.domain.enums import (
    AttemptStatus,
    ScrapingMethod,
    ValidationDecision,
)
from apps.api.src.modules.scraping.infrastructure.database.mappers.scraping_attempt_mapper import (
    ScrapingAttemptMapper,
)


def test_converts_running_attempt_without_optional_values() -> None:
    """Tentativa running ainda não possui decisão, scores ou erro."""

    attempt = ScrapingAttempt(
        job_id=uuid4(),
        method=ScrapingMethod.BEAUTIFULSOUP,
    )

    model = ScrapingAttemptMapper.to_model(attempt)
    restored = ScrapingAttemptMapper.to_entity(model)

    assert model.status == "running"
    assert model.decision is None
    assert restored.status is AttemptStatus.RUNNING
    assert restored.decision is None
    assert restored.quality_score is None


def test_converts_finished_attempt_with_scores_and_lists() -> None:
    """Decisão, scores, problems e warnings devem ser preservados."""

    attempt = ScrapingAttempt(
        job_id=uuid4(),
        method=ScrapingMethod.BEAUTIFULSOUP,
    )
    attempt.finish_validation(
        decision=ValidationDecision.FALLBACK,
        technical_score=0.90,
        text_score=0.20,
        evidence_score=0.10,
        quality_score=0.37,
        problems=["insufficient_text"],
        warnings=["limited_text"],
    )

    restored = ScrapingAttemptMapper.to_entity(
        ScrapingAttemptMapper.to_model(attempt)
    )

    assert restored.status is AttemptStatus.FALLBACK
    assert restored.decision is ValidationDecision.FALLBACK
    assert restored.quality_score == 0.37
    assert restored.problems == ["insufficient_text"]
    assert restored.warnings == ["limited_text"]


def test_updates_existing_attempt_model() -> None:
    """Model running deve ser atualizado após a validação."""

    attempt = ScrapingAttempt(
        job_id=uuid4(),
        method=ScrapingMethod.BEAUTIFULSOUP,
    )
    model = ScrapingAttemptMapper.to_model(attempt)

    attempt.fail("Timeout.")
    ScrapingAttemptMapper.update_model(model, attempt)

    assert model.status == "failed"
    assert model.error_message == "Timeout."
    assert model.finished_at == attempt.finished_at


def test_preserves_agent_review_fields() -> None:
    """Campos da investigacao por agente devem ir e voltar do model."""

    attempt = ScrapingAttempt(
        job_id=uuid4(),
        method=ScrapingMethod.BEAUTIFULSOUP,
    )
    attempt.finish_validation(
        decision=ValidationDecision.ACCEPT,
        technical_score=1.0,
        text_score=0.80,
        evidence_score=0.40,
        quality_score=0.64,
        problems=[],
        warnings=["semantic_reviewed", "agent_reviewed"],
        semantic_confidence=0.72,
        agent_reviewed=True,
        agent_reason="Agente encontrou evidencia complementar.",
    )

    restored = ScrapingAttemptMapper.to_entity(
        ScrapingAttemptMapper.to_model(attempt)
    )

    assert restored.semantic_confidence == 0.72
    assert restored.agent_reviewed is True
    assert restored.agent_reason == "Agente encontrou evidencia complementar."
