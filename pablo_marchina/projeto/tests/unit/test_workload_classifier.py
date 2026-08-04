from __future__ import annotations

from src.services.product.workload_classifier import classify_workloads, recommended_technologies


def _families(text: str) -> list[str]:
    return [match.family for match in classify_workloads(text)]


def test_conversational_ai_does_not_expand_to_unrelated_workloads() -> None:
    text = (
        "Conversational AI platform using NLP, machine learning and intelligent agents "
        "for customer interaction, marketing and service automation."
    )
    matches = classify_workloads(text)
    assert [match.family for match in matches] == ["llm_nlp"]
    technologies = recommended_technologies(matches)
    assert "NVIDIA NIM" in technologies
    assert "NVIDIA Isaac" not in technologies
    assert "NVIDIA Omniverse" not in technologies
    assert "NVIDIA Morpheus" not in technologies
    assert "RAPIDS" not in technologies


def test_drone_imagery_with_computer_vision_is_not_robotics() -> None:
    text = "Computer vision and machine learning over drone imagery for weed detection."
    assert _families(text) == ["computer_vision"]


def test_generic_healthcare_workflow_is_not_medical_imaging() -> None:
    text = "AI and data science for digital care workflows and patient journey coordination."
    assert "medical_imaging" not in _families(text)


def test_credit_risk_maps_to_tabular_ml() -> None:
    text = "Machine learning for agricultural credit risk and credit scoring."
    assert _families(text) == ["tabular_ml"]
