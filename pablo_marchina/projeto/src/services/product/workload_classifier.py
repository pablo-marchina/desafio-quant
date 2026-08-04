from __future__ import annotations

"""Evidence-weighted NVIDIA workload classification.

The classifier deliberately avoids sector-only and generic business words. A
workload family is returned only when the company text contains concrete
technical phrases that imply a compatible NVIDIA runtime.
"""

from dataclasses import dataclass
import re
import unicodedata


@dataclass(frozen=True)
class WorkloadMatch:
    family: str
    score: float
    matched_phrases: tuple[str, ...]
    technologies: tuple[str, ...]
    label: str


_FAMILY_CONFIG: dict[str, dict[str, object]] = {
    "llm_nlp": {
        "label": "LLM, NLP and conversational AI",
        "phrases": {
            "large language model": 4.0,
            "modelo de linguagem": 4.0,
            "generative ai": 4.0,
            "ia generativa": 4.0,
            "retrieval augmented generation": 4.0,
            "natural language processing": 3.5,
            "processamento de linguagem natural": 3.5,
            "conversational ai": 3.5,
            "inteligencia artificial conversacional": 3.5,
            "chatbot": 3.0,
            "virtual assistant": 3.0,
            "assistente virtual": 3.0,
            "semantic search": 3.0,
            "document intelligence": 3.0,
            "text classification": 2.5,
            "llm": 4.0,
            "nlp": 3.0,
            "rag": 3.0,
        },
        "technologies": (
            "NVIDIA NIM",
            "TensorRT-LLM",
            "NVIDIA NeMo",
            "Triton Inference Server",
        ),
    },
    "voice": {
        "label": "Speech and voice AI",
        "phrases": {
            "speech recognition": 4.0,
            "automatic speech recognition": 4.0,
            "speech to text": 4.0,
            "text to speech": 4.0,
            "voice bot": 4.0,
            "voice assistant": 3.5,
            "assistente de voz": 3.5,
            "audio transcription": 3.5,
            "transcricao de audio": 3.5,
            "call transcription": 3.5,
            "asr": 3.5,
            "tts": 3.5,
        },
        "technologies": (
            "NVIDIA Riva",
            "Triton Inference Server",
            "NVIDIA NIM",
        ),
    },
    "computer_vision": {
        "label": "Computer vision and video analytics",
        "phrases": {
            "computer vision": 4.0,
            "visao computacional": 4.0,
            "object detection": 4.0,
            "deteccao de objetos": 4.0,
            "image recognition": 3.5,
            "reconhecimento de imagens": 3.5,
            "visual inspection": 3.5,
            "inspecao visual": 3.5,
            "video analytics": 3.5,
            "image analytics": 3.5,
            "drone imagery": 3.0,
            "satellite imagery": 3.0,
            "optical character recognition": 3.0,
            "ocr": 2.5,
        },
        "technologies": (
            "TensorRT",
            "Triton Inference Server",
            "NVIDIA NIM",
        ),
    },
    "tabular_ml": {
        "label": "Tabular ML, forecasting and accelerated analytics",
        "phrases": {
            "predictive analytics": 4.0,
            "analise preditiva": 4.0,
            "credit scoring": 4.0,
            "credit risk model": 4.0,
            "fraud detection": 4.0,
            "deteccao de fraude": 4.0,
            "demand forecasting": 4.0,
            "time series forecasting": 4.0,
            "series temporais": 3.5,
            "forecasting": 3.0,
            "risk modeling": 3.5,
            "modelo de risco": 3.5,
            "tabular data": 3.0,
            "big data": 3.5,
            "data science": 3.0,
            "enterprise analytics": 3.0,
            "accelerated analytics": 4.0,
            "data pipeline": 3.0,
            "feature engineering": 3.0,
            "machine learning for credit": 3.5,
        },
        "technologies": (
            "RAPIDS",
            "cuDF",
            "cuML",
        ),
    },
    "robotics_simulation": {
        "label": "Robotics, autonomous systems and simulation",
        "phrases": {
            "industrial robotics": 4.0,
            "robotics": 4.0,
            "robotica": 4.0,
            "autonomous robot": 4.0,
            "robo autonomo": 4.0,
            "digital twin": 4.0,
            "gemeo digital": 4.0,
            "robot simulation": 4.0,
            "simulacao robotica": 4.0,
            "isaac sim": 4.0,
            "autonomous vehicle": 4.0,
        },
        "technologies": (
            "NVIDIA Isaac",
            "NVIDIA Omniverse",
        ),
    },
    "cybersecurity": {
        "label": "AI cybersecurity and threat analytics",
        "phrases": {
            "cybersecurity": 4.0,
            "ciberseguranca": 4.0,
            "threat detection": 4.0,
            "deteccao de ameacas": 4.0,
            "security operations": 3.5,
            "network anomaly": 3.5,
            "malware detection": 3.5,
        },
        "technologies": (
            "NVIDIA Morpheus",
            "RAPIDS",
        ),
    },
    "medical_imaging": {
        "label": "Medical imaging AI",
        "phrases": {
            "medical imaging": 4.0,
            "imagem medica": 4.0,
            "radiology": 4.0,
            "radiologia": 4.0,
            "pathology image": 4.0,
            "imagem patologica": 4.0,
            "mri": 3.5,
            "ct scan": 3.5,
            "tomografia": 3.5,
            "clinical imaging": 3.5,
        },
        "technologies": (
            "MONAI",
            "NVIDIA Clara",
            "TensorRT",
        ),
    },
}

_AGENT_PHRASES = (
    "ai agent",
    "agente de ia",
    "agentic ai",
    "multi agent",
    "multiagente",
    "tool calling",
)
_GOVERNANCE_PHRASES = (
    "guardrails",
    "ai safety",
    "seguranca de ia",
    "prompt injection",
    "content moderation",
    "policy enforcement",
)


def normalize_workload_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value or ""))
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", re.sub(r"[^a-zA-Z0-9+.-]+", " ", ascii_text).casefold()).strip()


def classify_workloads(
    text: str,
    *,
    max_families: int = 2,
    minimum_score: float = 3.0,
) -> list[WorkloadMatch]:
    normalized = normalize_workload_text(text)
    if not normalized:
        return []

    matches: list[WorkloadMatch] = []
    for family, raw in _FAMILY_CONFIG.items():
        phrase_weights = raw["phrases"]
        assert isinstance(phrase_weights, dict)
        matched: list[str] = []
        score = 0.0
        for phrase, weight in phrase_weights.items():
            if re.search(rf"(?<![a-z0-9]){re.escape(str(phrase))}(?![a-z0-9])", normalized):
                matched.append(str(phrase))
                score += float(weight)
        # Multiple independent technical phrases increase confidence, but a
        # repeated generic word cannot create another workload family.
        if len(matched) >= 2:
            score += min(2.0, 0.5 * (len(matched) - 1))
        if score >= minimum_score:
            matches.append(
                WorkloadMatch(
                    family=family,
                    score=round(score, 3),
                    matched_phrases=tuple(matched),
                    technologies=tuple(raw["technologies"]),
                    label=str(raw["label"]),
                )
            )

    matches.sort(key=lambda item: (-item.score, item.family))
    return matches[: max(0, max_families)]


def recommended_technologies(matches: list[WorkloadMatch], *, limit: int = 5) -> list[str]:
    result: list[str] = []
    for match in matches:
        for technology in match.technologies:
            if technology not in result:
                result.append(technology)
    return result[: max(0, limit)]


def needs_guardrails(text: str) -> bool:
    normalized = normalize_workload_text(text)
    return any(phrase in normalized for phrase in (*_AGENT_PHRASES, *_GOVERNANCE_PHRASES))
