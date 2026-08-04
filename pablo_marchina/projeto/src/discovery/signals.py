from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from src.quantitative.params import (
    DISCOVERY_CONFIDENCE_WEIGHTS,
    KNOWLEDGE_BASE_SIGNAL_BOOSTS,
    MAX_SIGNAL_BOOST,
)


def detect_ai_native_signals(
    text: str,
    *,
    source_url: str = "",
    source_id: str = "",
) -> dict[str, Any]:
    if not text:
        return {
            "signals": [],
            "signal_count": 0,
            "confidence_contribution": 0.0,
            "evidence_excerpts": [],
        }

    signals: list[dict[str, Any]] = []
    evidence_excerpts: list[dict[str, Any]] = []
    total_boost = 0.0

    for pattern, label, boost in KNOWLEDGE_BASE_SIGNAL_BOOSTS:
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        if matches:
            signals.append(
                {
                    "signal": label,
                    "keyword": pattern.strip("\\b"),
                    "boost": boost,
                    "count": len(matches),
                }
            )
            total_boost += boost * min(len(matches), 3)
            excerpt_start = max(0, matches[0].start() - 40)
            excerpt_end = min(len(text), matches[0].end() + 40)
            excerpt = text[excerpt_start:excerpt_end].strip()
            evidence_excerpts.append(
                {
                    "excerpt": excerpt,
                    "signal": label,
                    "source_url": source_url,
                    "source_id": source_id,
                    "collected_at": datetime.now(UTC).isoformat(),
                }
            )

    total_boost = min(total_boost, MAX_SIGNAL_BOOST)
    if total_boost > 0:
        total_boost = round(total_boost, 2)

    return {
        "signals": signals,
        "signal_count": len(signals),
        "confidence_contribution": total_boost,
        "evidence_excerpts": evidence_excerpts,
        "has_nvidia_tech": any(
            s["signal"]
            in (
                "Mentions NVIDIA TensorRT",
                "Mentions NVIDIA Triton Inference Server",
                "Mentions NVIDIA RAPIDS",
                "Mentions NVIDIA NeMo",
                "Mentions CUDA",
            )
            for s in signals
        ),
    }


def calculate_confidence(
    *,
    has_name: bool = False,
    has_website: bool = False,
    signal_contribution: float = 0.0,
    is_manual_seed: bool = False,
    source_reliable: bool = False,
) -> float:
    base = 0.0
    if has_name:
        base += DISCOVERY_CONFIDENCE_WEIGHTS["has_name"]
    if has_website:
        base += DISCOVERY_CONFIDENCE_WEIGHTS["has_website"]
    if is_manual_seed:
        base += DISCOVERY_CONFIDENCE_WEIGHTS["is_manual_seed"]
    if source_reliable:
        base += DISCOVERY_CONFIDENCE_WEIGHTS["source_reliable"]

    total = base + signal_contribution
    return round(max(0.0, min(1.0, total)), 2)
