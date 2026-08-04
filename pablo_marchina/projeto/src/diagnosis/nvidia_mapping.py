"""NVIDIA Technology Mapping — deterministic matrix from TechnicalGap to NVIDIA technologies."""

from __future__ import annotations

from src.diagnosis.schemas import GapWithEvidence, NvidiaTechnologyCandidate
from src.extraction.schemas import TechnicalGap

# ---------------------------------------------------------------------------
# Mapping matrix (deterministic; from docs/13_nvidia_mapping_matrix.md)
# ---------------------------------------------------------------------------

_TECH_MATRIX: dict[TechnicalGap, list[tuple[str, str]]] = {
    TechnicalGap.EXTERNAL_API_DEPENDENCY: [
        (
            "NVIDIA NIM",
            "NIM provides optimized microservices for inference, reducing external API dependencies.",
        ),
        (
            "NVIDIA AI Enterprise",
            "Enterprise-grade support for production deployments replacing third-party APIs.",
        ),
    ],
    TechnicalGap.HIGH_INFERENCE_COST: [
        (
            "TensorRT-LLM",
            "TensorRT-LLM optimizes LLM inference on NVIDIA GPUs, reducing cost per token.",
        ),
        (
            "Triton Inference Server",
            "Triton manages multi-model inference efficiently, lowering total infrastructure cost.",
        ),
        (
            "NVIDIA NIM",
            "NIM packages optimized models for cost-efficient self-hosted inference.",
        ),
    ],
    TechnicalGap.HIGH_LATENCY: [
        (
            "TensorRT-LLM",
            "TensorRT-LLM reduces latency through kernel fusion and quantization.",
        ),
        (
            "Triton Inference Server",
            "Triton enables concurrent model execution and dynamic batching for low latency.",
        ),
        (
            "NVIDIA NIM",
            "NIM offers pre-optimized inference endpoints with minimal overhead.",
        ),
    ],
    TechnicalGap.AGENT_GOVERNANCE_GAP: [
        (
            "NeMo Guardrails",
            "NeMo Guardrails provides programmable guardrails for LLM-based agents.",
        ),
        (
            "NVIDIA NeMo",
            "NeMo framework offers tooling for building and governing AI agents.",
        ),
    ],
    TechnicalGap.OBSERVABILITY_GAP: [
        (
            "NVIDIA AI Enterprise",
            "AI Enterprise includes model monitoring and observability tooling for production.",
        ),
    ],
    TechnicalGap.MODEL_EVALUATION_GAP: [
        (
            "NVIDIA NeMo",
            "NeMo provides evaluation harnesses for LLM benchmarking and testing.",
        ),
    ],
    TechnicalGap.PRIVACY_OR_CONTROLLED_DEPLOYMENT_GAP: [
        (
            "NVIDIA AI Enterprise",
            "AI Enterprise supports secure, on-premise deployments for regulated industries.",
        ),
        (
            "NVIDIA NIM",
            "NIM can be deployed on-prem with full data sovereignty.",
        ),
    ],
    TechnicalGap.SLOW_DATA_PIPELINE: [
        (
            "NVIDIA RAPIDS",
            "RAPIDS suite (cuDF, cuML) accelerates data pipelines on GPU.",
        ),
        (
            "cuDF",
            "cuDF provides GPU-accelerated DataFrame operations for faster ETL.",
        ),
        (
            "cuML",
            "cuML accelerates ML model training and inference on tabular data.",
        ),
    ],
    TechnicalGap.HEAVY_TABULAR_PROCESSING: [
        (
            "NVIDIA RAPIDS",
            "RAPIDS accelerates tabular data processing and ML on GPU.",
        ),
        (
            "cuML",
            "cuML provides GPU-accelerated implementations of common ML algorithms.",
        ),
    ],
    TechnicalGap.VOICE_NEED: [
        (
            "NVIDIA Riva",
            "Riva provides GPU-accelerated speech-to-text and text-to-speech.",
        ),
        (
            "NVIDIA NIM",
            "NIM includes optimized voice AI microservices for production.",
        ),
    ],
    TechnicalGap.SIMULATION_NEED: [
        (
            "NVIDIA Omniverse",
            "Omniverse enables physics-accurate simulation and digital twin creation.",
        ),
    ],
    TechnicalGap.COMPUTER_VISION_NEED: [
        (
            "NVIDIA AI Enterprise",
            "AI Enterprise includes TensorRT-optimized computer vision pipelines.",
        ),
        (
            "NVIDIA TensorRT",
            "TensorRT optimizes CV model inference for real-time applications.",
        ),
        (
            "NVIDIA NIM",
            "NIM provides pre-built CV inference microservices.",
        ),
    ],
    TechnicalGap.ROBOTICS_NEED: [
        (
            "NVIDIA Isaac",
            "Isaac platform provides robotics simulation, training, and deployment.",
        ),
        (
            "NVIDIA Omniverse",
            "Omniverse enables photorealistic simulation for robotics training.",
        ),
    ],
    TechnicalGap.HEALTHCARE_COMPLIANCE_NEED: [
        (
            "NVIDIA Clara",
            "Clara provides healthcare-specific AI frameworks and compliance tooling.",
        ),
        (
            "MONAI",
            "MONAI offers medical imaging AI with built-in compliance support.",
        ),
        (
            "NVIDIA AI Enterprise",
            "AI Enterprise ensures HIPAA-compliant deployments for healthcare AI.",
        ),
    ],
    TechnicalGap.AI_CYBERSECURITY_NEED: [
        (
            "NVIDIA Morpheus",
            "Morpheus provides GPU-accelerated cybersecurity AI pipeline.",
        ),
    ],
}

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def map_gap_to_technologies(gap: TechnicalGap) -> list[NvidiaTechnologyCandidate]:
    """Return all NVIDIA technology candidates for a single gap.

    Parameters
    ----------
    gap:
        The technical gap to map.

    Returns
    -------
    list[NvidiaTechnologyCandidate]
        Each with technology name and justification.
    """
    mappings = _TECH_MATRIX.get(gap, [])
    return [
        NvidiaTechnologyCandidate(
            technology_name=name,
            addresses_gap=gap,
            justification=justification,
        )
        for name, justification in mappings
    ]


def build_technology_candidates(
    diagnosed_gaps: list[GapWithEvidence],
) -> list[NvidiaTechnologyCandidate]:
    """Build a flat list of NVIDIA technology candidates from diagnosed gaps.

    Only gaps that were *detected* generate candidates.

    Parameters
    ----------
    diagnosed_gaps:
        List of gap diagnosis results.

    Returns
    -------
    list[NvidiaTechnologyCandidate]
        Deduplicated by (technology_name, gap) pair.
    """
    seen: set[tuple[str, str]] = set()
    candidates: list[NvidiaTechnologyCandidate] = []

    for gap_ev in diagnosed_gaps:
        if not gap_ev.detected:
            continue
        for candidate in map_gap_to_technologies(gap_ev.gap):
            key = (candidate.technology_name, candidate.addresses_gap.value)
            if key not in seen:
                seen.add(key)
                candidates.append(candidate)

    return candidates
