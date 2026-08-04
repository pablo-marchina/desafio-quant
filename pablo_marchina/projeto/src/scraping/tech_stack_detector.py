from __future__ import annotations

import re
from typing import Any

# ── Signal definitions ────────────────────────────────────────────────────

LLM_SIGNALS: list[tuple[re.Pattern, str, float]] = [
    (re.compile(r"gpt-?4|gpt-?3\.5|claude|gemini|llama", re.IGNORECASE), "llm_api", 0.7),
    (re.compile(r"langchain|llamaindex|haystack|semantic.?kernel", re.IGNORECASE), "llm_framework", 0.6),
    (re.compile(r"fine.?tun|RAG|retrieval.augment|embedding", re.IGNORECASE), "llm_technique", 0.5),
    (re.compile(r"prompt.?engin|chain-of-thought|agent.?loop|tool.?use", re.IGNORECASE), "llm_pattern", 0.5),
    (re.compile(r"openai|anthropic|cohere|mistral|together\.ai|groq", re.IGNORECASE), "llm_provider", 0.6),
]

GPU_SIGNALS: list[tuple[re.Pattern, str, float]] = [
    (re.compile(r"CUDA|cuDNN|TensorRT", re.IGNORECASE), "nvidia_gpu", 0.9),
    (re.compile(r"A100|H100|V100|T4|L4|RTX\s\d+", re.IGNORECASE), "nvidia_hardware", 0.8),
    (re.compile(r"PyTorch|TensorFlow.*GPU|JAX|cuDF|cuML", re.IGNORECASE), "gpu_framework", 0.5),
    (re.compile(r"GPU.?accelerat|GPU.?train|GPU.?infer", re.IGNORECASE), "gpu_usage", 0.4),
]

INFERENCE_SIGNALS: list[tuple[re.Pattern, str, float]] = [
    (re.compile(r"Triton|vLLM|TGI|text.?generation.?inference", re.IGNORECASE), "inference_engine", 0.8),
    (re.compile(r"model.?serv|model.?deploy|inference.?endpoint", re.IGNORECASE), "inference_need", 0.4),
    (re.compile(r"latency|throughput|batch.?infer|model.?optim", re.IGNORECASE), "inference_concern", 0.3),
]

DATA_SIGNALS: list[tuple[re.Pattern, str, float]] = [
    (re.compile(r"spark|hadoop|kafka|airflow|data.?pipe", re.IGNORECASE), "data_pipeline", 0.5),
    (re.compile(r"postgres|mysql|mongo|redis|elastic", re.IGNORECASE), "database", 0.3),
    (re.compile(r"data.?science|analytics|dashboard|BI|tableau", re.IGNORECASE), "data_analytics", 0.3),
]

DEVOPS_SIGNALS: list[tuple[re.Pattern, str, float]] = [
    (re.compile(r"kubernetes|k8s|docker|helm|terraform", re.IGNORECASE), "container_orchestration", 0.6),
    (re.compile(r"CI/CD|github.?actions|gitlab.?ci|jenkins", re.IGNORECASE), "ci_cd", 0.4),
    (re.compile(r"aws|gcp|azure|cloud.?comput", re.IGNORECASE), "cloud_provider", 0.3),
]

ALL_SIGNAL_GROUPS: list[tuple[str, list[tuple[re.Pattern, str, float]]]] = [
    ("llm", LLM_SIGNALS),
    ("gpu", GPU_SIGNALS),
    ("inference", INFERENCE_SIGNALS),
    ("data", DATA_SIGNALS),
    ("devops", DEVOPS_SIGNALS),
]

# ── Career-specific keyword detection ─────────────────────────────────────

CAREER_ROLE_PATTERNS: dict[str, list[str]] = {
    "ML Engineer": ["machine learning engineer", "ml engineer", "deep learning engineer"],
    "Data Scientist": ["data scientist", "data science"],
    "AI Engineer": ["ai engineer", "artificial intelligence engineer"],
    "Backend Engineer": ["backend engineer", "back-end engineer", "software engineer"],
    "NLP Engineer": ["nlp engineer", "natural language processing"],
    "Computer Vision Engineer": ["computer vision", "cv engineer"],
    "MLOps Engineer": ["mlops", "machine learning ops", "model deployment engineer"],
}

CAREER_TECH_KEYWORDS: dict[str, float] = {
    "PyTorch": 0.9,
    "TensorFlow": 0.8,
    "JAX": 0.7,
    "CUDA": 0.95,
    "Kubernetes": 0.5,
    "Docker": 0.4,
    "AWS": 0.3,
    "GCP": 0.3,
    "Azure": 0.3,
    "Rust": 0.3,
    "Go": 0.3,
    "Python": 0.2,
    "RAG": 0.7,
    "LLM": 0.8,
    "NLP": 0.6,
    "Transformers": 0.7,
    "ONNX": 0.6,
    "TensorRT": 0.9,
    "vLLM": 0.9,
}


# ── Data classes ──────────────────────────────────────────────────────────


class TechSignal:
    """A detected technology signal from scraped content."""

    def __init__(self, category: str, signal_type: str, confidence: float, matched_text: str):
        self.category = category
        self.signal_type = signal_type
        self.confidence = confidence
        self.matched_text = matched_text

    def __repr__(self) -> str:
        return f"TechSignal({self.category}/{self.signal_type}, conf={self.confidence})"


class CareerInsights:
    """Insights extracted from a careers/jobs page."""

    def __init__(self, roles: list[dict[str, Any]], tech_requirements: list[dict[str, Any]]):
        self.roles = roles
        self.tech_requirements = tech_requirements


# ── Detectors ─────────────────────────────────────────────────────────────


class TechStackDetector:
    """Detect technology stack signals from scraped text and HTML."""

    def detect(self, text: str, html: str | None = None) -> list[TechSignal]:
        """Scan *text* for technology signals across all groups."""
        signals: list[TechSignal] = []
        for group_name, patterns in ALL_SIGNAL_GROUPS:
            for pattern, signal_type, confidence in patterns:
                for match in pattern.finditer(text):
                    signals.append(
                        TechSignal(
                            category=group_name,
                            signal_type=signal_type,
                            confidence=confidence,
                            matched_text=match.group(),
                        )
                    )
        # Dedup by signal_type (keep highest confidence)
        seen: dict[str, TechSignal] = {}
        for s in signals:
            existing = seen.get(s.signal_type)
            if existing is None or s.confidence > existing.confidence:
                seen[s.signal_type] = s
        return list(seen.values())

    def detect_from_html(self, html: str) -> list[TechSignal]:
        """Detect signals from raw HTML (including meta tags, scripts, etc.)."""
        text = html
        signals = self.detect(text)

        # Check for JS framework / CDN hints in script src
        script_srcs = re.findall(r'<script[^>]+src="([^"]+)"', html, re.IGNORECASE)
        for src in script_srcs:
            src_lower = src.lower()
            for hint, signal_type in [
                ("react", "react"),
                ("angular", "angular"),
                ("vue", "vue"),
                ("next.js", "nextjs"),
                ("nuxt", "nuxt"),
                ("svelte", "svelte"),
                ("jquery", "jquery"),
            ]:
                if hint in src_lower:
                    if not any(s.signal_type == signal_type for s in signals):
                        signals.append(TechSignal(category="frontend", signal_type=signal_type, confidence=0.3, matched_text=src))
                    break

        return signals


def analyze_careers_page(text: str) -> CareerInsights:
    """Extract role and tech-requirement signals from a careers page.

    Args:
        text: Clean extracted text from a careers / jobs page.

    Returns:
        CareerInsights with detected roles and technology requirements.
    """
    text_lower = text.lower()

    roles: list[dict[str, Any]] = []
    for role_name, keywords in CAREER_ROLE_PATTERNS.items():
        for kw in keywords:
            if kw in text_lower:
                roles.append({"role": role_name, "keyword": kw})
                break

    tech_requirements: list[dict[str, Any]] = []
    for tech, confidence in CAREER_TECH_KEYWORDS.items():
        if tech.lower() in text_lower:
            tech_requirements.append({"technology": tech, "confidence": confidence})

    return CareerInsights(roles=roles, tech_requirements=tech_requirements)
