"""Testes das entidades do modulo startups."""

from uuid import uuid4

import pytest

from apps.api.src.modules.startups.domain.entities import Startup, StartupAIProfile, StartupEvidence
from apps.api.src.modules.startups.domain.enums import (
    AiDeploymentStage,
    AiGpuNeed,
    AiMaturityLevel,
    AiWorkloadType,
    FundingStage,
    StartupEvidenceType,
)
from apps.api.src.modules.startups.domain.exceptions import InvalidStartupDataError


def test_startup_normalizes_basic_fields() -> None:
    startup = Startup(
        name="  Acme AI  ",
        website_url=" https://acme.example.com ",
        sector=" AI Infra ",
        country=" BR ",
    )

    assert startup.name == "Acme AI"
    assert startup.website_url == "https://acme.example.com"
    assert startup.sector == "AI Infra"
    assert startup.country == "BR"


def test_startup_requires_name() -> None:
    with pytest.raises(InvalidStartupDataError):
        Startup(name=" ")


def test_update_changes_fields_and_timestamp() -> None:
    startup = Startup(name="Old")
    previous_updated_at = startup.updated_at

    startup.update(name="New", description=" nova descricao ")

    assert startup.name == "New"
    assert startup.description == "nova descricao"
    assert startup.updated_at >= previous_updated_at


def test_classify_sets_level_reason_and_timestamp() -> None:
    startup = Startup(name="Acme AI")

    startup.classify(AiMaturityLevel.AI_NATIVE, "  Modelos proprios no core.  ")

    assert startup.ai_maturity_level is AiMaturityLevel.AI_NATIVE
    assert startup.classification_reason == "Modelos proprios no core."
    assert startup.classified_at is not None


def test_classify_requires_reason() -> None:
    startup = Startup(name="Acme AI")

    with pytest.raises(InvalidStartupDataError):
        startup.classify(AiMaturityLevel.NON_AI, "   ")


def test_update_sets_structured_fields() -> None:
    startup = Startup(name="Acme AI")

    startup.update(
        founders=["  Ana Silva  ", "Bruno Costa", ""],
        funding_stage=FundingStage.SEED,
        funding_amount_usd=500_000.0,
        customers=["Empresa X", "  Empresa Y  "],
    )

    assert startup.founders == ("Ana Silva", "Bruno Costa")
    assert startup.funding_stage is FundingStage.SEED
    assert startup.funding_amount_usd == 500_000.0
    assert startup.customers == ("Empresa X", "Empresa Y")


def test_update_rejects_negative_funding_amount() -> None:
    startup = Startup(name="Acme AI")

    with pytest.raises(InvalidStartupDataError):
        startup.update(funding_amount_usd=-1.0)


def test_startup_rejects_negative_funding_amount_on_creation() -> None:
    with pytest.raises(InvalidStartupDataError):
        Startup(name="Acme AI", funding_amount_usd=-1.0)


def test_startup_defaults_founders_and_customers_to_empty_tuple() -> None:
    startup = Startup(name="Acme AI")

    assert startup.founders == ()
    assert startup.customers == ()


def test_evidence_requires_source_url() -> None:
    with pytest.raises(InvalidStartupDataError):
        StartupEvidence(
            startup_id=uuid4(),
            scraping_result_id=uuid4(),
            source_url=" ",
        )


def test_evidence_validates_confidence_score() -> None:
    with pytest.raises(InvalidStartupDataError):
        StartupEvidence(
            startup_id=uuid4(),
            scraping_result_id=uuid4(),
            source_url="https://example.com",
            confidence_score=1.2,
        )


def test_evidence_defaults_type_to_other() -> None:
    evidence = StartupEvidence(
        startup_id=uuid4(),
        scraping_result_id=uuid4(),
        source_url="https://example.com",
    )

    assert evidence.evidence_type is StartupEvidenceType.OTHER


def test_startup_ai_profile_defaults_to_unknown() -> None:
    profile = StartupAIProfile()

    assert profile.ai_workload_type is AiWorkloadType.UNKNOWN
    assert profile.gpu_need is AiGpuNeed.UNKNOWN
    assert profile.deployment_stage is AiDeploymentStage.UNKNOWN
    assert profile.current_tools == ()
    assert profile.field_confidence == {}


def test_update_ai_profile_sets_profile_and_updates_timestamp() -> None:
    startup = Startup(name="Acme AI")
    original_updated_at = startup.updated_at

    profile = StartupAIProfile(
        ai_workload_type=AiWorkloadType.NLP,
        gpu_need=AiGpuNeed.HIGH,
        current_tools=("PyTorch",),
    )
    startup.update_ai_profile(profile)

    assert startup.ai_profile is profile
    assert startup.updated_at > original_updated_at


def test_startup_ai_profile_is_initially_none() -> None:
    startup = Startup(name="New Startup")

    assert startup.ai_profile is None


def test_update_field_audit_persists_confidence_and_evidence_ids() -> None:
    startup = Startup(name="Acme AI")
    original_updated_at = startup.updated_at

    startup.update_field_audit(
        field_confidence={"founders": 0.9, "sector": 0.75},
        field_evidence_ids={"founders": ["ev-1", "ev-2"]},
    )

    assert startup.field_confidence == {"founders": 0.9, "sector": 0.75}
    assert startup.field_evidence_ids == {"founders": ["ev-1", "ev-2"]}
    assert startup.updated_at > original_updated_at


def test_startup_field_audit_defaults_are_empty_dicts() -> None:
    startup = Startup(name="New Startup")

    assert startup.field_confidence == {}
    assert startup.field_evidence_ids == {}
