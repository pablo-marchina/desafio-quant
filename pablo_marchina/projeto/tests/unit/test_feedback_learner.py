"""Tests for feedback_learner integration in the pipeline."""

from __future__ import annotations

from src.decisioning.feedback_learner import apply_feedback_weight, learn_feedback_weight
from src.orchestration.state import ProductWorkflowState


class TestApplyFeedbackWeight:
    def test_no_feedback_returns_base(self) -> None:
        assert apply_feedback_weight(0.5) == 0.5

    def test_positive_feedback_increases_weight(self) -> None:
        result = apply_feedback_weight(0.5, positive=3)
        assert result == 0.59  # 0.5 + 3 * 0.03

    def test_negative_feedback_decreases_weight(self) -> None:
        result = apply_feedback_weight(0.5, negative=2)
        assert result == 0.4  # 0.5 - 2 * 0.05

    def test_clamped_to_one(self) -> None:
        result = apply_feedback_weight(0.95, positive=3)
        assert result == 1.0

    def test_clamped_to_zero(self) -> None:
        result = apply_feedback_weight(0.1, negative=3)
        assert result == 0.0

    def test_mixed_feedback(self) -> None:
        result = apply_feedback_weight(0.5, positive=2, negative=1)
        assert result == 0.51  # 0.5 + 2*0.03 - 1*0.05

    def test_zero_base_adjustment(self) -> None:
        result = apply_feedback_weight(0.0, positive=1)
        assert result == 0.03

    def test_full_base_negative_adjustment(self) -> None:
        result = apply_feedback_weight(1.0, negative=1)
        assert result == 0.95

    def test_rounding_four_decimals(self) -> None:
        result = apply_feedback_weight(0.3333, positive=1, negative=2)
        assert result == 0.2633  # 0.3333 + 0.03 - 0.10

    def test_learn_feedback_weight_exposes_quantitative_adjustment(self) -> None:
        result = learn_feedback_weight(0.3, positive=1)
        assert result["adjusted_weight"] == 0.34
        assert result["sample_size"] == 1.0
        assert result["confidence"] == 0.2
        assert result["uncertainty"] == 0.8


class TestApplyFeedbackWeightsNode:
    def test_skipped_when_no_feedback(self) -> None:
        import src.orchestration.node_impl  # noqa: F401
        from src.orchestration.nodes import WORKFLOW_NODES

        node = next(n for n in WORKFLOW_NODES if n.name == "apply_feedback_weights")
        state = ProductWorkflowState(
            workflow_id="test",
            feedback_counts={},
            iteration_count=0,
        )
        result = node.fn(state)
        assert result.status == "skipped"
        assert result.state_updates["iteration_count"] == 0

    def test_adjusts_weights_from_feedback(self) -> None:
        import src.orchestration.node_impl  # noqa: F401
        from src.orchestration.nodes import WORKFLOW_NODES

        node = next(n for n in WORKFLOW_NODES if n.name == "apply_feedback_weights")
        state = ProductWorkflowState(
            workflow_id="test",
            feedback_counts={
                "confidence": {"positive": 1, "negative": 0},
            },
            iteration_count=0,
        )
        result = node.fn(state)
        assert result.status == "completed"
        assert "confidence" in result.state_updates["adjusted_weights"]
        assert "confidence" in result.state_updates["feedback_adjustments"]
        assert result.state_updates["iteration_count"] == 1
        # base weight = 0.30, sample_confidence=0.20, boundary_damping=0.80
        assert result.state_updates["adjusted_weights"]["confidence"] == 0.34

    def test_clears_feedback_counts_after_apply(self) -> None:
        import src.orchestration.node_impl  # noqa: F401
        from src.orchestration.nodes import WORKFLOW_NODES

        node = next(n for n in WORKFLOW_NODES if n.name == "apply_feedback_weights")
        state = ProductWorkflowState(
            workflow_id="test",
            feedback_counts={"business_impact": {"positive": 2}},
            iteration_count=0,
        )
        result = node.fn(state)
        assert result.state_updates["feedback_counts"] == {}


class TestRouteAfterFeedback:
    @staticmethod
    def _routing_function(state: ProductWorkflowState) -> str:
        if state.review_decision == "request_more_evidence" and state.iteration_count < state.max_iterations:
            return "score_startup_probabilistic"
        return "finish"

    def test_loops_back_when_request_more_evidence(self) -> None:
        state = ProductWorkflowState(
            workflow_id="test",
            review_decision="request_more_evidence",
            iteration_count=0,
            max_iterations=3,
        )
        assert self._routing_function(state) == "score_startup_probabilistic"

    def test_loops_back_with_remaining_iterations(self) -> None:
        state = ProductWorkflowState(
            workflow_id="test",
            review_decision="request_more_evidence",
            iteration_count=1,
            max_iterations=3,
        )
        assert self._routing_function(state) == "score_startup_probabilistic"

    def test_goes_to_finish_when_approved(self) -> None:
        state = ProductWorkflowState(
            workflow_id="test",
            review_decision="approve",
            iteration_count=0,
            max_iterations=3,
        )
        assert self._routing_function(state) == "finish"

    def test_goes_to_finish_when_max_iterations_reached(self) -> None:
        state = ProductWorkflowState(
            workflow_id="test",
            review_decision="request_more_evidence",
            iteration_count=3,
            max_iterations=3,
        )
        assert self._routing_function(state) == "finish"

    def test_goes_to_finish_when_iterations_exceeded(self) -> None:
        state = ProductWorkflowState(
            workflow_id="test",
            review_decision="request_more_evidence",
            iteration_count=5,
            max_iterations=3,
        )
        assert self._routing_function(state) == "finish"

    def test_goes_to_finish_when_empty_review_decision(self) -> None:
        state = ProductWorkflowState(
            workflow_id="test",
            review_decision="",
            iteration_count=0,
            max_iterations=3,
        )
        assert self._routing_function(state) == "finish"

    def test_goes_to_finish_on_reject_decision(self) -> None:
        state = ProductWorkflowState(
            workflow_id="test",
            review_decision="reject",
            iteration_count=0,
            max_iterations=3,
        )
        assert self._routing_function(state) == "finish"
