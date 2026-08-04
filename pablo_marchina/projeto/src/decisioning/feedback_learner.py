from __future__ import annotations


def apply_feedback_weight(base_weight: float, *, positive: int = 0, negative: int = 0) -> float:
    adjustment = positive * 0.03 - negative * 0.05
    return round(max(0.0, min(1.0, base_weight + adjustment)), 4)


def learn_feedback_weight(
    base_weight: float,
    *,
    positive: int = 0,
    negative: int = 0,
    prior_samples: int = 4,
    max_adjustment: float = 0.25,
) -> dict[str, float | str]:
    sample_size = max(0, positive) + max(0, negative)
    bounded_base = _clamp(base_weight)
    if sample_size == 0:
        return {
            "base_weight": round(bounded_base, 4),
            "adjusted_weight": round(bounded_base, 4),
            "positive_rate": 0.0,
            "negative_rate": 0.0,
            "net_feedback_signal": 0.0,
            "sample_size": 0.0,
            "learning_rate": 0.0,
            "confidence": 0.0,
            "uncertainty": 1.0,
            "adjustment": 0.0,
            "formula": "no feedback samples; adjusted_weight=base_weight",
        }

    positive_rate = max(0, positive) / sample_size
    negative_rate = max(0, negative) / sample_size
    net_signal = positive_rate - negative_rate
    confidence = sample_size / (sample_size + max(1, prior_samples))
    boundary_damping = 1.0 - abs(bounded_base - 0.5)
    learning_rate = min(max_adjustment, confidence * max_adjustment * boundary_damping)
    adjustment = net_signal * learning_rate
    adjusted = _clamp(bounded_base + adjustment)
    return {
        "base_weight": round(bounded_base, 4),
        "adjusted_weight": round(adjusted, 4),
        "positive_rate": round(positive_rate, 4),
        "negative_rate": round(negative_rate, 4),
        "net_feedback_signal": round(net_signal, 4),
        "sample_size": float(sample_size),
        "learning_rate": round(learning_rate, 4),
        "confidence": round(confidence, 4),
        "uncertainty": round(1.0 - confidence, 4),
        "adjustment": round(adjustment, 4),
        "formula": (
            "adjusted_weight=clamp(base_weight + ((positive_rate-negative_rate)"
            "*min(max_adjustment, sample_confidence*max_adjustment*boundary_damping)))"
        ),
    }


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
