from __future__ import annotations

from pathlib import Path

from pydantic import HttpUrl

from src.classification.ai_native_classifier import classify_ai_native
from src.classification.ai_native_model import load_jsonl, predict_ai_native, save_model, train_token_model
from src.extraction.schemas import AINativeLevel, StartupProfile


def _profile() -> StartupProfile:
    return StartupProfile(
        startup_name="VisionOps",
        website=HttpUrl("https://vision.example.com"),
        sector="Computer Vision",
        description="AI-powered computer vision platform using deep learning for inspection.",
        product_summary="Computer vision is the core product value.",
        ai_signals=["deep learning", "computer vision", "AI-powered"],
        tech_stack_signals=["PyTorch", "TensorRT"],
        sources=[],
        confidence_score=0.8,
    )


def test_classifier_exposes_probabilities_and_uncertainty_without_changing_result() -> None:
    result = classify_ai_native(_profile())

    assert result.classification in {AINativeLevel.AI_NATIVE, AINativeLevel.AI_ENABLED}
    assert result.probabilities
    assert abs(sum(result.probabilities.values()) - 1.0) < 0.01
    assert 0.0 <= result.uncertainty <= 1.0
    assert result.classification_features


def test_train_token_model_and_predict_from_saved_model(tmp_path: Path) -> None:
    records = load_jsonl(Path("data/eval/ai_native_labeled_ptbr.jsonl"))
    model = train_token_model(records)
    model_path = tmp_path / "model.json"
    save_model(model, model_path)

    prediction = predict_ai_native(_profile(), model_path=model_path)

    assert prediction.model_available is True
    assert prediction.predicted_class in set(AINativeLevel)
    assert abs(sum(prediction.probabilities.values()) - 1.0) < 0.01
    assert prediction.confidence_score == max(prediction.probabilities.values())
