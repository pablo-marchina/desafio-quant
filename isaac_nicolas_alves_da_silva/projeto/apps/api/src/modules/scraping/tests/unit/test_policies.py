"""Testes unitários das políticas de decisão do domínio."""

import pytest

from apps.api.src.modules.scraping.domain.enums import ValidationDecision
from apps.api.src.modules.scraping.domain.policies import (
    ContentAcceptancePolicy,
    FallbackPolicy,
    LLMReviewPolicy,
    ValidationDecisionPolicy,
    ValidationSummary,
)


@pytest.fixture
def decision_policy() -> ValidationDecisionPolicy:
    """Cria a política completa usada pelos diferentes cenários."""

    return ValidationDecisionPolicy(
        acceptance_policy=ContentAcceptancePolicy(),
        fallback_policy=FallbackPolicy(),
    )


def test_accepts_high_quality_content_without_blockers(
    decision_policy: ValidationDecisionPolicy,
) -> None:
    """Conteúdo bom deve ser aceito sem tentar outra tecnologia."""

    summary = ValidationSummary(
        technical_score=0.95,
        text_score=0.85,
        evidence_score=0.80,
        quality_score=0.85,
    )

    decision = decision_policy.decide(
        summary,
        has_next_strategy=True,
    )

    assert decision is ValidationDecision.ACCEPT


def test_blocking_problem_rejects_even_with_maximum_score(
    decision_policy: ValidationDecisionPolicy,
) -> None:
    """Um captcha bloqueia aceitação mesmo com scores altos."""

    summary = ValidationSummary(
        technical_score=1.0,
        text_score=1.0,
        evidence_score=1.0,
        quality_score=1.0,
        problems={"captcha"},
    )

    decision = decision_policy.decide(
        summary,
        has_next_strategy=True,
    )

    assert decision is ValidationDecision.REJECT


def test_recoverable_problem_uses_fallback_when_strategy_exists(
    decision_policy: ValidationDecisionPolicy,
) -> None:
    """Texto insuficiente permite tentar uma próxima tecnologia."""

    summary = ValidationSummary(
        technical_score=0.90,
        text_score=0.20,
        evidence_score=0.10,
        quality_score=0.37,
        problems={"insufficient_text"},
    )

    decision = decision_policy.decide(
        summary,
        has_next_strategy=True,
    )

    assert decision is ValidationDecision.FALLBACK


def test_recoverable_problem_rejects_without_another_strategy(
    decision_policy: ValidationDecisionPolicy,
) -> None:
    """Sem próxima tecnologia, um conteúdo ruim precisa ser rejeitado."""

    summary = ValidationSummary(
        technical_score=0.90,
        text_score=0.20,
        evidence_score=0.10,
        quality_score=0.37,
        problems={"insufficient_text"},
    )

    decision = decision_policy.decide(
        summary,
        has_next_strategy=False,
    )

    assert decision is ValidationDecision.REJECT


def test_link_farm_uses_fallback_even_with_high_score(
    decision_policy: ValidationDecisionPolicy,
) -> None:
    """Pagina de docs com navegacao densa em links: tenta outra estrategia.

    Reproduz https://nvidia.github.io/TensorRT-LLM/ (NVIDIA Knowledge V2):
    BS4 mede link_ratio sobre o HTML bruto e marca link_farm mesmo com score
    alto (sidebar de navegacao tipica de docs Sphinx/MkDocs, nao spam real).
    """

    summary = ValidationSummary(
        technical_score=1.0,
        text_score=0.6152,
        evidence_score=0.35,
        quality_score=0.8076,
        problems={"link_farm"},
        warnings={"no_ai_evidence_signal", "high_link_ratio"},
    )

    decision = decision_policy.decide(
        summary,
        has_next_strategy=True,
    )

    assert decision is ValidationDecision.FALLBACK


def test_llm_review_policy_selects_only_ambiguous_usable_content() -> None:
    policy = LLMReviewPolicy()
    ambiguous = ValidationSummary(
        technical_score=0.90,
        text_score=0.80,
        evidence_score=0.30,
        quality_score=0.62,
    )

    assert policy.requires_review(ambiguous) is True


def test_llm_review_policy_ignores_clear_or_blocked_content() -> None:
    policy = LLMReviewPolicy()
    clear = ValidationSummary(
        technical_score=1.0,
        text_score=0.95,
        evidence_score=0.90,
        quality_score=0.90,
    )
    blocked = ValidationSummary(
        technical_score=1.0,
        text_score=0.80,
        evidence_score=0.30,
        quality_score=0.62,
        problems={"captcha"},
    )

    assert policy.requires_review(clear) is False
    assert policy.requires_review(blocked) is False
