from __future__ import annotations


def calibrate_threshold(values: list[float], *, default: float = 0.7) -> float:
    if not values:
        return default
    ordered = sorted(max(0.0, min(1.0, value)) for value in values)
    return round(ordered[len(ordered) // 2], 4)
