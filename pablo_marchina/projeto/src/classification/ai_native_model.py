from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.extraction.schemas import AINativeLevel, ConfidenceLevel, StartupProfile

MODEL_PATH = Path("models/ai_native_classifier/model.json")
MODEL_VERSION = "ai-native-token-nb-v1"
TOKEN_RE = re.compile(r"[a-zA-Z0-9_+\-.]+")


class ClassificationPrediction(BaseModel):
    startup_name: str
    predicted_class: AINativeLevel
    probabilities: dict[str, float]
    confidence_score: float = Field(ge=0.0, le=1.0)
    uncertainty: float = Field(ge=0.0, le=1.0)
    model_version: str
    model_available: bool = False
    calibration_status: str = "heuristic_prior"
    features_used: list[str] = Field(default_factory=list)


def predict_ai_native(
    profile: StartupProfile,
    *,
    heuristic_classification: AINativeLevel | None = None,
    heuristic_confidence: ConfidenceLevel | None = None,
    model_path: Path = MODEL_PATH,
) -> ClassificationPrediction:
    if model_path.exists():
        try:
            return _predict_with_model(profile, model_path)
        except Exception:
            pass
    return _prediction_from_heuristic(profile, heuristic_classification, heuristic_confidence)


def train_token_model(records: list[dict[str, Any]]) -> dict[str, Any]:
    class_counts: Counter[str] = Counter()
    token_counts: dict[str, Counter[str]] = defaultdict(Counter)
    vocabulary: set[str] = set()
    for record in records:
        label = str(record["label"])
        tokens = _tokens_from_record(record)
        if not tokens:
            continue
        class_counts[label] += 1
        token_counts[label].update(tokens)
        vocabulary.update(tokens)

    if not class_counts:
        raise ValueError("No labeled records with tokens were provided.")

    return {
        "model_version": MODEL_VERSION,
        "class_counts": dict(class_counts),
        "token_counts": {label: dict(counts) for label, counts in token_counts.items()},
        "vocabulary": sorted(vocabulary),
        "record_count": sum(class_counts.values()),
        "labels": sorted(class_counts),
    }


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            raw = line.strip()
            if not raw:
                continue
            record = json.loads(raw)
            if "label" not in record:
                raise ValueError(f"Missing label at {path}:{line_no}")
            records.append(record)
    return records


def save_model(model: dict[str, Any], path: Path = MODEL_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(model, indent=2, sort_keys=True), encoding="utf-8")


def _predict_with_model(profile: StartupProfile, model_path: Path) -> ClassificationPrediction:
    model = json.loads(model_path.read_text(encoding="utf-8"))
    tokens = _tokens_from_profile(profile)
    labels = list(model.get("labels", []))
    if not labels:
        raise ValueError("Model has no labels.")

    class_counts = {label: float(model["class_counts"].get(label, 0.0)) for label in labels}
    token_counts = {label: Counter(model["token_counts"].get(label, {})) for label in labels}
    vocabulary = set(model.get("vocabulary", []))
    vocab_size = max(1, len(vocabulary))
    total_records = max(1.0, sum(class_counts.values()))

    log_scores: dict[str, float] = {}
    for label in labels:
        total_tokens = sum(token_counts[label].values())
        log_score = math.log((class_counts[label] + 1.0) / (total_records + len(labels)))
        for token in tokens:
            token_count = token_counts[label].get(token, 0)
            log_score += math.log((token_count + 1.0) / (total_tokens + vocab_size))
        log_scores[label] = log_score

    probabilities = _softmax(log_scores)
    predicted = max(probabilities, key=probabilities.get)
    confidence = probabilities[predicted]
    return ClassificationPrediction(
        startup_name=profile.startup_name,
        predicted_class=AINativeLevel(predicted),
        probabilities=probabilities,
        confidence_score=round(confidence, 4),
        uncertainty=round(1.0 - confidence, 4),
        model_version=str(model.get("model_version", MODEL_VERSION)),
        model_available=True,
        calibration_status="local_jsonl_trained",
        features_used=sorted(set(tokens)),
    )


def _prediction_from_heuristic(
    profile: StartupProfile,
    classification: AINativeLevel | None,
    confidence: ConfidenceLevel | None,
) -> ClassificationPrediction:
    predicted = classification or AINativeLevel.NON_AI
    confidence_score = {
        ConfidenceLevel.HIGH: 0.82,
        ConfidenceLevel.MEDIUM: 0.62,
        ConfidenceLevel.LOW: 0.42,
        None: 0.34,
    }[confidence]
    labels = [item.value for item in AINativeLevel]
    remaining = max(0.0, 1.0 - confidence_score)
    other_share = remaining / max(1, len(labels) - 1)
    probabilities = {label: round(other_share, 4) for label in labels}
    probabilities[predicted.value] = round(confidence_score, 4)
    return ClassificationPrediction(
        startup_name=profile.startup_name,
        predicted_class=predicted,
        probabilities=probabilities,
        confidence_score=round(confidence_score, 4),
        uncertainty=round(1.0 - confidence_score, 4),
        model_version="heuristic-prior-v1",
        model_available=False,
        calibration_status="heuristic_prior",
        features_used=sorted(set(_tokens_from_profile(profile))),
    )


def _tokens_from_record(record: dict[str, Any]) -> list[str]:
    text = " ".join(
        str(record.get(key, ""))
        for key in ("startup_name", "description", "product_summary", "sector")
    )
    text += " " + " ".join(str(item) for item in record.get("ai_signals", []))
    text += " " + " ".join(str(item) for item in record.get("tech_stack_signals", []))
    return _tokenize(text)


def _tokens_from_profile(profile: StartupProfile) -> list[str]:
    return _tokenize(
        " ".join(
            [
                profile.startup_name,
                profile.sector,
                profile.description,
                profile.product_summary,
                " ".join(profile.ai_signals),
                " ".join(profile.tech_stack_signals),
            ]
        )
    )


def _tokenize(text: str) -> list[str]:
    return [match.group(0).casefold() for match in TOKEN_RE.finditer(text) if len(match.group(0)) >= 2]


def _softmax(log_scores: dict[str, float]) -> dict[str, float]:
    max_log = max(log_scores.values())
    exps = {label: math.exp(value - max_log) for label, value in log_scores.items()}
    total = sum(exps.values()) or 1.0
    return {label: round(value / total, 4) for label, value in exps.items()}
