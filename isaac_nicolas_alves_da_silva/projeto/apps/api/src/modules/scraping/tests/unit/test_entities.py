"""Testes unitários das entidades do domínio de scraping."""

from uuid import uuid4

import pytest

from apps.api.src.modules.scraping.domain.entities import (
    ScrapingAttempt,
    ScrapingJob,
)
from apps.api.src.modules.scraping.domain.enums import (
    AttemptStatus,
    JobStatus,
    ScrapingMethod,
    ValidationDecision,
)
from apps.api.src.modules.scraping.domain.exceptions import (
    InvalidJobTransitionError,
)


def test_new_job_starts_pending() -> None:
    """Todo job novo deve aguardar execução."""

    job = ScrapingJob(url="https://example.com")

    assert job.status is JobStatus.PENDING
    assert job.started_at is None
    assert job.finished_at is None
    assert job.result_id is None


def test_job_can_follow_successful_lifecycle() -> None:
    """Um job pode seguir de pending para running e completed."""

    job = ScrapingJob(url="https://example.com")
    result_id = uuid4()

    job.start()
    job.complete(result_id)

    assert job.status is JobStatus.COMPLETED
    assert job.started_at is not None
    assert job.finished_at is not None
    assert job.result_id == result_id


def test_pending_job_cannot_complete_directly() -> None:
    """A entidade deve bloquear a transição pending para completed."""

    job = ScrapingJob(url="https://example.com")

    with pytest.raises(InvalidJobTransitionError):
        job.complete(uuid4())


def test_running_job_can_fail_with_reason() -> None:
    """Falhas conhecidas devem finalizar o job com uma mensagem."""

    job = ScrapingJob(url="https://example.com")

    job.start()
    job.fail("Nenhuma estratégia produziu conteúdo válido.")

    assert job.status is JobStatus.FAILED
    assert job.error_message == "Nenhuma estratégia produziu conteúdo válido."
    assert job.finished_at is not None


def test_attempt_maps_fallback_decision_to_fallback_status() -> None:
    """A decisão de fallback deve gerar o estado correspondente."""

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
        warnings=[],
    )

    assert attempt.status is AttemptStatus.FALLBACK
    assert attempt.decision is ValidationDecision.FALLBACK
    assert attempt.quality_score == 0.37
    assert attempt.problems == ["insufficient_text"]
    assert attempt.finished_at is not None


def test_finished_attempt_cannot_fail_again() -> None:
    """Uma tentativa finalizada não pode receber outro estado final."""

    attempt = ScrapingAttempt(
        job_id=uuid4(),
        method=ScrapingMethod.BEAUTIFULSOUP,
    )
    attempt.finish_validation(
        decision=ValidationDecision.ACCEPT,
        technical_score=1.0,
        text_score=1.0,
        evidence_score=1.0,
        quality_score=1.0,
        problems=[],
        warnings=[],
    )

    with pytest.raises(InvalidJobTransitionError):
        attempt.fail("Erro tardio.")


# --- Testes dos campos e estados de investigação com agentes (v8) ---


def test_finish_validation_records_agent_audit_fields() -> None:
    """``finish_validation`` aceita e guarda os novos campos de auditoria."""

    attempt = ScrapingAttempt(
        job_id=uuid4(),
        method=ScrapingMethod.BEAUTIFULSOUP,
    )

    attempt.finish_validation(
        decision=ValidationDecision.ACCEPT,
        technical_score=1.0,
        text_score=0.90,
        evidence_score=0.80,
        quality_score=0.88,
        problems=[],
        warnings=["agent_reviewed", "agent_decision_accepted"],
        semantic_confidence=0.60,
        agent_reviewed=True,
        agent_reason="O agente confirmou evidências suficientes.",
    )

    assert attempt.status is AttemptStatus.ACCEPTED
    assert attempt.semantic_confidence == 0.60
    assert attempt.agent_reviewed is True
    assert attempt.agent_reason == "O agente confirmou evidências suficientes."


def test_finish_validation_defaults_agent_fields_when_not_provided() -> None:
    """No caminho v7 (sem agente), os novos campos ficam em seus padrões."""

    attempt = ScrapingAttempt(
        job_id=uuid4(),
        method=ScrapingMethod.BEAUTIFULSOUP,
    )

    attempt.finish_validation(
        decision=ValidationDecision.ACCEPT,
        technical_score=1.0,
        text_score=1.0,
        evidence_score=1.0,
        quality_score=1.0,
        problems=[],
        warnings=[],
    )

    assert attempt.semantic_confidence is None
    assert attempt.agent_reviewed is False
    assert attempt.agent_reason is None


def test_finish_needs_more_sources_sets_dedicated_status() -> None:
    """O agente pode pedir mais fontes sem produzir um ``ScrapingResult``."""

    attempt = ScrapingAttempt(
        job_id=uuid4(),
        method=ScrapingMethod.BEAUTIFULSOUP,
    )

    attempt.finish_needs_more_sources("É preciso encontrar mais fontes.")

    assert attempt.status is AttemptStatus.NEEDS_MORE_SOURCES
    assert attempt.agent_reviewed is True
    assert attempt.agent_reason == "É preciso encontrar mais fontes."
    assert attempt.decision is None
    assert attempt.finished_at is not None


def test_finish_needs_more_sources_requires_running_attempt() -> None:
    """Uma tentativa já finalizada não pode pedir mais fontes novamente."""

    attempt = ScrapingAttempt(
        job_id=uuid4(),
        method=ScrapingMethod.BEAUTIFULSOUP,
    )
    attempt.fail("Erro técnico qualquer.")

    with pytest.raises(InvalidJobTransitionError):
        attempt.finish_needs_more_sources("Mais fontes necessárias.")


def test_accept_sets_accepted_status_with_agent_metadata() -> None:
    """``accept`` é o caminho alternativo de aceitação confirmada por agente."""

    attempt = ScrapingAttempt(
        job_id=uuid4(),
        method=ScrapingMethod.BEAUTIFULSOUP,
    )

    attempt.accept(
        technical_score=1.0,
        text_score=0.90,
        evidence_score=0.80,
        quality_score=0.88,
        semantic_confidence=0.60,
        agent_reviewed=True,
    )

    assert attempt.status is AttemptStatus.ACCEPTED
    assert attempt.decision is ValidationDecision.ACCEPT
    assert attempt.problems == []
    assert attempt.warnings == []
    assert attempt.semantic_confidence == 0.60
    assert attempt.agent_reviewed is True
    assert attempt.finished_at is not None


def test_reject_sets_rejected_status_with_reason() -> None:
    """``reject`` registra a decisão de negócio e o motivo do agente."""

    attempt = ScrapingAttempt(
        job_id=uuid4(),
        method=ScrapingMethod.BEAUTIFULSOUP,
    )

    attempt.reject("O agente não encontrou evidências.", agent_reviewed=True)

    assert attempt.status is AttemptStatus.REJECTED
    assert attempt.decision is ValidationDecision.REJECT
    assert attempt.agent_reason == "O agente não encontrou evidências."
    assert attempt.agent_reviewed is True
    assert attempt.finished_at is not None
