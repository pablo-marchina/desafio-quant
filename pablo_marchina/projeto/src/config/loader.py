"""Centralized configuration loader for all YAML config files.

Loads, validates, and caches YAML configurations as Pydantic models.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from src.config.schemas import (
    EvalThresholdsConfig,
    KeywordsConfig,
    LLMRoutingConfig,
    RagRetrievalConfig,
    RerankingConfig,
    ScoringConfig,
    SourceQualityConfig,
)


def _load_yaml(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class ConfigLoaderService:
    """Singleton-like loader for all YAML configuration files.

    Caches configs after first load. Call ``reload()`` to invalidate cache.
    """

    _instance: ConfigLoaderService | None = None
    _config_dir: Path

    _scoring: ScoringConfig | None = None
    _source_quality: SourceQualityConfig | None = None
    _rag_retrieval: RagRetrievalConfig | None = None
    _reranking: RerankingConfig | None = None
    _eval_thresholds: EvalThresholdsConfig | None = None
    _llm_routing: LLMRoutingConfig | None = None
    _keywords: KeywordsConfig | None = None

    def __new__(cls, config_dir: str | Path = "config") -> ConfigLoaderService:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._config_dir = Path(config_dir)
        return cls._instance

    def reload(self) -> None:
        self._scoring = None
        self._source_quality = None
        self._rag_retrieval = None
        self._reranking = None
        self._eval_thresholds = None
        self._llm_routing = None
        self._keywords = None

    def _resolve(self, name: str) -> Path:
        return self._config_dir / name

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------
    def scoring(self) -> ScoringConfig:
        if self._scoring is None:
            raw = _load_yaml(self._resolve("scoring.yaml"))
            self._scoring = ScoringConfig.model_validate(raw)
        return self._scoring

    # ------------------------------------------------------------------
    # Source Quality
    # ------------------------------------------------------------------
    def source_quality(self) -> SourceQualityConfig:
        if self._source_quality is None:
            raw = _load_yaml(self._resolve("source_quality.yaml"))
            self._source_quality = SourceQualityConfig.model_validate(raw)
        return self._source_quality

    # ------------------------------------------------------------------
    # RAG Retrieval
    # ------------------------------------------------------------------
    def rag_retrieval(self) -> RagRetrievalConfig:
        if self._rag_retrieval is None:
            raw = _load_yaml(self._resolve("rag_retrieval.yaml"))
            self._rag_retrieval = RagRetrievalConfig.model_validate(raw)
        return self._rag_retrieval

    # ------------------------------------------------------------------
    # Reranking
    # ------------------------------------------------------------------
    def reranking(self) -> RerankingConfig:
        if self._reranking is None:
            raw = _load_yaml(self._resolve("reranking.yaml"))
            self._reranking = RerankingConfig.model_validate(raw)
        return self._reranking

    # ------------------------------------------------------------------
    # Evaluation Thresholds
    # ------------------------------------------------------------------
    def eval_thresholds(self) -> EvalThresholdsConfig:
        if self._eval_thresholds is None:
            raw = _load_yaml(self._resolve("eval_thresholds.yaml"))
            self._eval_thresholds = EvalThresholdsConfig.model_validate(raw)
        return self._eval_thresholds

    # ------------------------------------------------------------------
    # LLM Routing
    # ------------------------------------------------------------------
    def llm_routing(self) -> LLMRoutingConfig:
        if self._llm_routing is None:
            raw = _load_yaml(self._resolve("llm_routing.yaml"))
            self._llm_routing = LLMRoutingConfig.model_validate(raw)
        return self._llm_routing

    # ------------------------------------------------------------------
    # Keywords
    # ------------------------------------------------------------------
    def keywords(self) -> KeywordsConfig:
        if self._keywords is None:
            raw = _load_yaml(self._resolve("keywords.yaml"))
            self._keywords = KeywordsConfig.model_validate(raw)
        return self._keywords

    def gap_keyword_dict(self) -> dict[str, list[str]]:
        return self.keywords().gap_keyword_dict

    def knowledge_base_signal_boosts(self) -> list[dict[str, Any]]:
        return [item.model_dump() for item in self.keywords().knowledge_base_signal_boosts]

    def nvidia_keyword_boosts(self) -> dict[str, float]:
        return self.keywords().nvidia_keyword_boosts

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------
    def priority_score_weights(self) -> dict[str, float]:
        s = self.scoring().priority_score
        return s.model_dump()

    def confidence_float_map(self) -> dict[str, float]:
        return self.scoring().confidence.float_map.model_dump()

    def confidence_score_factors(self) -> dict[str, float]:
        return self.scoring().confidence.score_factors.model_dump()

    def confidence_thresholds(self) -> dict[str, float]:
        c = self.scoring().confidence.thresholds
        return {"high_min": c.high_min, "medium_min": c.medium_min}

    def source_type_scores(self) -> dict[str, float]:
        return self.source_quality().source_types.model_dump()

    def gap_business_impact(self) -> dict[str, float]:
        return self.source_quality().gap_business_impact

    def quality_gate_thresholds(self) -> dict[str, Any]:
        return self.eval_thresholds().quality_gates.model_dump()

    def workflow_thresholds(self) -> dict[str, Any]:
        return self.eval_thresholds().workflow.model_dump()

    @property
    def confidence_penalty_on_missing(self) -> float:
        return self.scoring().confidence.penalty_on_missing

    @property
    def max_signal_boost(self) -> float:
        return self.scoring().confidence.max_signal_boost

    @property
    def no_evidence_factor(self) -> float:
        return self.scoring().confidence.no_evidence_factor

    def validate_all(self) -> list[str]:
        errors: list[str] = []
        for method_name in [
            "scoring",
            "source_quality",
            "rag_retrieval",
            "reranking",
            "eval_thresholds",
            "llm_routing",
            "keywords",
        ]:
            try:
                getattr(self, method_name)()
            except Exception as exc:
                errors.append(f"{method_name}.yaml: {exc}")
        return errors
