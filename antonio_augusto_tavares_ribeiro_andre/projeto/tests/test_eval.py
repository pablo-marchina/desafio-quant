"""Testes do eval set rotulado (F1.12).

Garantem que o conjunto versionado em `data/eval/` carrega, cobre o espaço de rótulos
(3 classes × 5 regiões do plano `classe × AIMI`) e que o schema impõe a **coerência
direcional** da anotação (sanidade da rotulagem, não o corte calibrado de F6.4). Tudo
offline, como o loader de seeds (F0.9).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.eval import (
    ExpectedPillars,
    ExpectedTech,
    LabeledStartup,
    by_classification,
    by_region,
    class_distribution,
    load_eval_set,
)
from packages.schemas.aimi import band_for
from packages.schemas.enums import AIMIBand, AIMIPillar, Classification, PlaneRegion, Priority

_MIN_ENTRIES = 20  # DoD F1.12: conjunto inicial ≥20 startups.


def _entry(**overrides: object) -> LabeledStartup:
    """Constrói uma entrada válida (alvo_graduacao) e aplica overrides p/ os casos negativos."""
    base: dict[str, object] = {
        "id": "x",
        "nome": "X",
        "setor": "s",
        "descricao": "d",
        "classificacao": "AI-native",
        "region": "alvo_graduacao",
        "aimi": {
            "data_moat": 18,
            "workflow_depth": 16,
            "technical_optimization": 6,
            "distribution_moat": 12,
        },
        "rationale": "r",
        "synthetic": True,
    }
    base.update(overrides)
    return LabeledStartup.model_validate(base)


# --- carregamento e cobertura -------------------------------------------------


def test_loads_min_entries_with_unique_ids() -> None:
    es = load_eval_set()
    assert len(es) >= _MIN_ENTRIES
    assert len({e.id for e in es}) == len(es)


def test_covers_all_classes_and_regions() -> None:
    es = load_eval_set()
    assert {e.classificacao for e in es} == set(Classification)
    assert {e.region for e in es} == set(PlaneRegion)


def test_class_distribution_sums_to_total() -> None:
    dist = class_distribution()
    assert sum(dist.values()) == len(load_eval_set())
    assert all(v > 0 for v in dist.values())  # nenhuma classe vazia


def test_aimi_spans_low_and_high() -> None:
    totals = [e.aimi.total for e in load_eval_set()]
    assert min(totals) < 40 and max(totals) > 70  # espalhamento p/ correlação (F6.4)
    # ao menos um pilar na faixa Forte em algum lugar do conjunto.
    assert any(
        getattr(e.aimi, p.value) >= 19 for e in load_eval_set() for p in AIMIPillar
    )


# --- coerência por região (o que o ground-truth precisa garantir) -------------


def test_alvo_graduacao_is_the_graduation_target() -> None:
    for e in by_region(PlaneRegion.ALVO_GRADUACAO):
        assert e.classificacao is Classification.AI_NATIVE
        assert e.aimi.technical_optimization <= 8  # P3 baixo = upside NVIDIA
        assert max(e.aimi.data_moat, e.aimi.workflow_depth) >= 13  # P1 ou P2 forte
        assert e.expected_nvidia_techs  # contrato F7.2b: techs esperadas


def test_maduro_has_high_p3() -> None:
    for e in by_region(PlaneRegion.MADURO):
        assert e.aimi.technical_optimization >= 13


def test_non_ai_has_no_expected_techs() -> None:
    for e in by_classification(Classification.NON_AI):
        assert e.region is PlaneRegion.FORA_ESCOPO
        assert e.expected_nvidia_techs == []


# --- expected_techs: forma chapada x rica + view de nomes (F7.7, Passo 1) -----


def test_expected_techs_flat_form_parses_without_priority() -> None:
    """A forma chapada legada ('NVIDIA NIM') segue válida → ExpectedTech com prioridade None."""
    e = _entry(expected_nvidia_techs=["NVIDIA NIM", "TensorRT-LLM"])
    assert [t.tech for t in e.expected_techs] == ["NVIDIA NIM", "TensorRT-LLM"]
    assert all(t.prioridade is None for t in e.expected_techs)
    # view de nomes idêntica → a métrica de presença (F7.2b) não muda
    assert e.expected_nvidia_techs == ["NVIDIA NIM", "TensorRT-LLM"]


def test_expected_techs_rich_form_carries_priority() -> None:
    """A forma rica ({tech, prioridade}) carrega o rank; a view de nomes ignora a prioridade."""
    e = _entry(
        expected_nvidia_techs=[
            {"tech": "NVIDIA NIM", "prioridade": "alta"},
            {"tech": "NVIDIA Triton Inference Server", "prioridade": "media"},
        ]
    )
    assert e.expected_techs[0].prioridade is Priority.ALTA
    assert e.expected_techs[1].prioridade is Priority.MEDIA
    assert e.expected_nvidia_techs == ["NVIDIA NIM", "NVIDIA Triton Inference Server"]


def test_expected_techs_mixed_flat_and_rich() -> None:
    """Chapada e rica convivem na mesma lista (migração incremental do rótulo)."""
    e = _entry(expected_nvidia_techs=[{"tech": "NVIDIA NIM", "prioridade": "alta"}, "TensorRT-LLM"])
    assert e.expected_techs[0].prioridade is Priority.ALTA
    assert e.expected_techs[1].prioridade is None
    assert e.expected_nvidia_techs == ["NVIDIA NIM", "TensorRT-LLM"]


def test_expected_nvidia_techs_property_matches_names_in_loaded_set() -> None:
    """Em todo o eval set carregado, a view de nomes == os techs dos itens ricos (retrocompat)."""
    for e in load_eval_set():
        assert e.expected_nvidia_techs == [t.tech for t in e.expected_techs]


def test_expected_tech_rejects_unknown_priority() -> None:
    """Prioridade fora do enum §5.5 é rejeitada — sanidade do rótulo priorizado."""
    with pytest.raises(ValidationError):
        _entry(expected_nvidia_techs=[{"tech": "NVIDIA NIM", "prioridade": "altissima"}])


def test_expected_tech_construct_direct() -> None:
    """ExpectedTech isolado: prioridade default None; aceita o enum Priority."""
    assert ExpectedTech(tech="NVIDIA NIM").prioridade is None
    assert ExpectedTech(tech="NVIDIA NIM", prioridade=Priority.ALTA).prioridade is Priority.ALTA


# --- ExpectedPillars: total e faixa ------------------------------------------


def test_expected_pillars_total_and_band() -> None:
    p = ExpectedPillars(
        data_moat=20, workflow_depth=10, technical_optimization=5, distribution_moat=3
    )
    assert p.total == 38
    assert p.band(AIMIPillar.DATA_MOAT) is AIMIBand.FORTE
    assert p.band(AIMIPillar.WORKFLOW_DEPTH) is band_for(10)  # EMERGENTE
    assert p.band(AIMIPillar.TECHNICAL_OPTIMIZATION) is AIMIBand.AUSENTE


def test_pillar_score_out_of_range_rejected() -> None:
    with pytest.raises(ValidationError):
        ExpectedPillars(
            data_moat=26, workflow_depth=0, technical_optimization=0, distribution_moat=0
        )


# --- validações de coerência da anotação (casos negativos) --------------------


def test_region_fixes_class() -> None:
    with pytest.raises(ValidationError):  # wrapper exige AI-native
        _entry(region="wrapper", classificacao="AI-enabled")


def test_non_ai_cannot_have_deep_workflow() -> None:
    with pytest.raises(ValidationError):
        _entry(
            classificacao="non-AI",
            region="fora_escopo",
            aimi={
                "data_moat": 3,
                "workflow_depth": 15,
                "technical_optimization": 1,
                "distribution_moat": 4,
            },
        )


def test_alvo_graduacao_requires_low_p3() -> None:
    with pytest.raises(ValidationError):
        _entry(
            aimi={
                "data_moat": 18,
                "workflow_depth": 16,
                "technical_optimization": 15,  # P3 alto contradiz "alvo de graduação"
                "distribution_moat": 12,
            }
        )


def test_alvo_graduacao_requires_strong_p1_or_p2() -> None:
    with pytest.raises(ValidationError):
        _entry(
            aimi={
                "data_moat": 9,
                "workflow_depth": 8,  # nem P1 nem P2 estabelecido
                "technical_optimization": 5,
                "distribution_moat": 7,
            }
        )


def test_maduro_requires_high_p3() -> None:
    with pytest.raises(ValidationError):
        _entry(
            region="maduro",
            aimi={
                "data_moat": 18,
                "workflow_depth": 17,
                "technical_optimization": 10,  # P3 não estabelecido
                "distribution_moat": 18,
            },
        )


def test_real_entry_requires_evidence() -> None:
    with pytest.raises(ValidationError):  # synthetic=false sem evidence_urls
        _entry(synthetic=False)
    # com evidência, passa:
    e = _entry(synthetic=False, evidence_urls=["https://exemplo.com.br/sobre"])
    assert e.evidence_urls


def test_load_eval_set_is_cached() -> None:
    assert load_eval_set() is load_eval_set()
