from __future__ import annotations

from src.orchestration.node_impl import node_match_activation_playbooks
from src.orchestration.state import NodeStatus, ProductWorkflowState


class _FakeSession:
    def __init__(self) -> None:
        self.expired = False

    def expire_all(self) -> None:
        self.expired = True


class _FakeActivationRepo:
    def __init__(self) -> None:
        self.persisted = False

    def replace_recommendations_for_analysis_run(self, analysis_run_id, recs):  # noqa: ANN001
        assert analysis_run_id == "analysis-test"
        assert recs
        self.persisted = True


class _FakeActivationService:
    created: list["_FakeActivationService"] = []

    def __init__(self, session: _FakeSession) -> None:
        assert session.expired is True
        self.activation_repo = _FakeActivationRepo()
        self.__class__.created.append(self)

    def generate_recommendations_for_run(self, analysis_run_id: str):  # noqa: ANN201
        assert analysis_run_id == "analysis-test"
        return [{"id": "activation-1"}]


def test_activation_node_refreshes_session_before_reading_persisted_gaps_and_mappings(
    monkeypatch,  # noqa: ANN001
) -> None:
    _FakeActivationService.created.clear()
    monkeypatch.setattr(
        "src.orchestration.node_impl.ActivationPlaybookService",
        _FakeActivationService,
    )
    session = _FakeSession()
    state = ProductWorkflowState(
        workflow_id="workflow-test",
        analysis_run_id="analysis-test",
        metadata_json={"_session": session},
    )

    result = node_match_activation_playbooks(state)

    assert result.status == NodeStatus.COMPLETED
    assert result.state_updates["activation_recommendation_ids"] == ["activation-1"]
    assert _FakeActivationService.created[0].activation_repo.persisted is True
