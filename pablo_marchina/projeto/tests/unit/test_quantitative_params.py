"""Test centralized quantitative parameters — validity, consistency, and documentation."""

import inspect

import pytest

from src.quantitative.params import (
    CONFIDENCE_FLOAT_MAP,
    CONFIDENCE_SCORE_FACTORS,
    CONFIDENCE_THRESHOLDS,
    DEFENSIBILITY_WEIGHTS,
    DISCOVERY_CONFIDENCE_WEIGHTS,
    INCEPTION_FIT_WEIGHTS,
    OPPORTUNITY_SCORE_WEIGHTS,
    PRIORITY_SCORE_WEIGHTS,
    PRODUCTION_READINESS_WEIGHTS,
    SOURCE_QUALITY_SCORES,
    validate_all_weight_sets,
)

_WEIGHT_SETS: dict[str, dict[str, float]] = {
    "PRIORITY_SCORE_WEIGHTS": PRIORITY_SCORE_WEIGHTS,
    "OPPORTUNITY_SCORE_WEIGHTS": OPPORTUNITY_SCORE_WEIGHTS,
    "PRODUCTION_READINESS_WEIGHTS": PRODUCTION_READINESS_WEIGHTS,
    "DEFENSIBILITY_WEIGHTS": DEFENSIBILITY_WEIGHTS,
    "INCEPTION_FIT_WEIGHTS": INCEPTION_FIT_WEIGHTS,
}


class TestWeightSets:
    def test_all_weight_sets_sum_to_one(self) -> None:
        results = validate_all_weight_sets()
        for name, total in results.items():
            assert abs(total - 1.0) < 1e-6, f"{name} sums to {total}, not 1.0"

    def test_each_weight_set_has_positive_weights(self) -> None:
        for name, weights in _WEIGHT_SETS.items():
            for key, val in weights.items():
                assert val > 0, f"{name}[{key}] = {val}, must be positive"

    @pytest.mark.parametrize("name,weights", list(_WEIGHT_SETS.items()))
    def test_weight_set_keys_are_strings(self, name: str, weights: dict[str, float]) -> None:
        for key in weights:
            assert isinstance(key, str), f"{name} has non-string key: {key!r}"

    def test_no_empty_weight_sets(self) -> None:
        for name, weights in _WEIGHT_SETS.items():
            assert len(weights) >= 2, f"{name} has {len(weights)} weight(s), expected >= 2"


class TestNumericRanges:
    def test_confidence_float_map_values_in_valid_range(self) -> None:
        for level, val in CONFIDENCE_FLOAT_MAP.items():
            assert 0.0 <= val <= 1.0, f"{level}={val} outside [0, 1]"

    def test_confidence_score_factors_values_in_valid_range(self) -> None:
        for level, val in CONFIDENCE_SCORE_FACTORS.items():
            assert 0.0 <= val <= 1.0, f"{level}={val} outside [0, 1]"

    def test_confidence_thresholds_consistent(self) -> None:
        high_min = CONFIDENCE_THRESHOLDS["high_min"]
        medium_min = CONFIDENCE_THRESHOLDS["medium_min"]
        assert (
            0.0 < medium_min < high_min < 1.0
        ), f"Threshold order violated: high_min={high_min}, medium_min={medium_min}"

    def test_source_quality_scores_descending(self) -> None:
        scores = list(SOURCE_QUALITY_SCORES.values())
        for i in range(len(scores) - 1):
            assert (
                scores[i] >= scores[i + 1]
            ), f"SOURCE_QUALITY_SCORES not descending at index {i}: {scores[i]} < {scores[i + 1]}"

    def test_discovery_confidence_weights_reasonable(self) -> None:
        total = sum(DISCOVERY_CONFIDENCE_WEIGHTS.values())
        assert total < 1.0, (
            f"DISCOVERY_CONFIDENCE_WEIGHTS sum = {total}, expected < 1.0 " "(signal_contribution adds to total)"
        )


class TestConsistency:
    def test_confidence_levels_match_between_maps(self) -> None:
        float_levels = set(CONFIDENCE_FLOAT_MAP.keys())
        factor_levels = set(CONFIDENCE_SCORE_FACTORS.keys())
        assert float_levels == factor_levels, f"Mismatched levels: float_map={float_levels}, factors={factor_levels}"
        # NOTE: CONFIDENCE_FLOAT_MAP and CONFIDENCE_SCORE_FACTORS have documented
        # discrepancies (low=0.3 vs 0.4). TODO: unify per params.py docstring.

    def test_validate_all_weight_sets_returns_expected_keys(self) -> None:
        results = validate_all_weight_sets()
        assert set(results.keys()) == set(_WEIGHT_SETS.keys())


class TestDocumentation:
    def test_module_has_docstring(self) -> None:
        import src.quantitative.params as mod

        doc = mod.__doc__
        assert doc is not None and len(doc) > 50, "params.py missing module-level docstring"

    def test_each_weight_set_is_documented_in_yaml(self) -> None:
        """Values now come from YAML config, check the scoring.yaml has all weight sets."""
        from src.config.loader import ConfigLoaderService

        cfg = ConfigLoaderService()
        s = cfg.scoring()
        yaml_names = {
            "PRIORITY_SCORE_WEIGHTS": s.priority_score.model_dump(),
            "OPPORTUNITY_SCORE_WEIGHTS": s.opportunity_score.model_dump(),
            "PRODUCTION_READINESS_WEIGHTS": s.production_readiness.model_dump(),
            "DEFENSIBILITY_WEIGHTS": s.defensibility.model_dump(),
            "INCEPTION_FIT_WEIGHTS": s.inception_fit.model_dump(),
        }
        for name, expected in yaml_names.items():
            actual = _WEIGHT_SETS[name]
            assert actual == expected, f"{name} mismatch: YAML={expected}, params={actual}"
