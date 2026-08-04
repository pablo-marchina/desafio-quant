"""Testes da funcao pura _key_missing_fields (regra de parada do enriquecimento).

Condicao de parada: (campos-chave preenchidos) OU (MAX_ENRICHMENT_ROUNDS).
Campos-chave: ai_workload_type, deployment_stage, gpu_need.
founders/funding/customers nao disparam enriquecimento sozinhos.
"""

from apps.api.src.modules.orchestration.application.ports import StartupProfileSnapshot
from apps.api.src.modules.orchestration.application.use_cases.advance_url_ingestion_job import (
    _key_missing_fields,
)


def _profile(**overrides) -> StartupProfileSnapshot:
    defaults = dict(
        name="Acme",
        website_url="https://acme.example.com",
        founders=[],
        funding_stage=None,
        customers=[],
        evidence_urls=[],
        ai_workload_type="unknown",
        deployment_stage="unknown",
        gpu_need="unknown",
    )
    defaults.update(overrides)
    return StartupProfileSnapshot(**defaults)


def test_all_key_fields_unknown_triggers_enrichment() -> None:
    result = _key_missing_fields(_profile())
    assert "ai_workload_type" in result
    assert "deployment_stage" in result
    assert "gpu_need" in result


def test_all_key_fields_filled_stops_enrichment() -> None:
    result = _key_missing_fields(
        _profile(
            ai_workload_type="nlp",
            deployment_stage="production",
            gpu_need="high",
        )
    )
    assert result == []


def test_only_gpu_need_unknown_still_triggers() -> None:
    result = _key_missing_fields(
        _profile(
            ai_workload_type="vision",
            deployment_stage="pilot",
            gpu_need="unknown",
        )
    )
    assert result == ["gpu_need"]


def test_founders_absent_but_key_fields_ok_does_not_trigger() -> None:
    # founders/funding/customers ausentes nao sao campos-chave —
    # nao devem causar enriquecimento por conta propria.
    result = _key_missing_fields(
        _profile(
            ai_workload_type="nlp",
            deployment_stage="mvp",
            gpu_need="medium",
            founders=[],           # ausente
            funding_stage=None,    # ausente
            customers=[],          # ausente
        )
    )
    assert result == []


def test_only_deployment_stage_unknown() -> None:
    result = _key_missing_fields(
        _profile(
            ai_workload_type="analytics",
            deployment_stage="unknown",
            gpu_need="low",
        )
    )
    assert result == ["deployment_stage"]


def test_returns_all_three_when_all_unknown() -> None:
    result = _key_missing_fields(_profile())
    assert set(result) == {"ai_workload_type", "deployment_stage", "gpu_need"}
