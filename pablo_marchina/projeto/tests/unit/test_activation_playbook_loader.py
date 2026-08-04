from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.playbook.loader import load_playbooks
from src.playbook.schemas import ActivationPlaybook


def _make_minimal_playbook(playbook_id: str = "test_pb") -> dict:
    return {
        "playbook_id": playbook_id,
        "name": "Test Playbook",
        "description": "A test playbook",
        "target_gap_types": ["high_latency"],
        "target_claim_types": ["gap_claim"],
        "nvidia_technologies": ["TensorRT"],
        "technical_experiment": {
            "title": "Test Experiment",
            "hypothesis": "Test hypothesis",
            "description": "Test description",
            "duration": "2 weeks",
        },
        "success_metrics": ["latency"],
        "recommended_motion": "technical_workshop",
        "prerequisites": ["GPU access"],
        "evidence_requirements": ["Evidence of latency"],
        "risks": ["None"],
        "expected_value": "50% reduction",
        "implementation_complexity": "medium",
        "confidence_rules": {
            "requires_gap_match": True,
            "evidence_coverage_boost": True,
            "unsupported_claim_penalty": True,
            "min_evidence_coverage": 0.3,
        },
        "output_template": {
            "section_title": "Recommended Activation Playbook",
            "fields": ["playbook_name", "technical_experiment"],
        },
        "version": "1.0",
    }


def _write_playbooks(tmp_path: Path, playbooks: list[dict]) -> Path:
    path = tmp_path / "playbooks.yaml"
    with path.open("w", encoding="utf-8") as f:
        yaml.dump({"playbooks": playbooks}, f)
    return path


def test_load_valid_playbooks(tmp_path: Path) -> None:
    pb = _make_minimal_playbook("test_1")
    path = _write_playbooks(tmp_path, [pb])
    result = load_playbooks(path)
    assert len(result) == 1
    assert isinstance(result[0], ActivationPlaybook)
    assert result[0].playbook_id == "test_1"
    assert result[0].name == "Test Playbook"
    assert result[0].target_gap_types == ["high_latency"]
    assert result[0].version == "1.0"


def test_load_validates_all_10_playbooks(tmp_path: Path) -> None:
    pbs = [_make_minimal_playbook(f"pb_{i}") for i in range(10)]
    path = _write_playbooks(tmp_path, pbs)
    result = load_playbooks(path)
    assert len(result) == 10


def test_load_fails_on_empty_playbooks(tmp_path: Path) -> None:
    path = _write_playbooks(tmp_path, [])
    with pytest.raises(ValueError, match="contains no playbooks"):
        load_playbooks(path)


def test_load_fails_on_missing_playbooks_key(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    with path.open("w", encoding="utf-8") as f:
        yaml.dump({"not_playbooks": []}, f)
    with pytest.raises(ValueError, match="top-level 'playbooks' key"):
        load_playbooks(path)


def test_load_fails_on_duplicate_ids(tmp_path: Path) -> None:
    pb = _make_minimal_playbook("dup_id")
    path = _write_playbooks(tmp_path, [pb, pb])
    with pytest.raises(ValueError, match="Duplicate playbook_id"):
        load_playbooks(path)


def test_load_fails_on_missing_playbook_id(tmp_path: Path) -> None:
    pb = _make_minimal_playbook()
    del pb["playbook_id"]
    path = _write_playbooks(tmp_path, [pb])
    with pytest.raises(ValueError, match="missing 'playbook_id'"):
        load_playbooks(path)


def test_load_fails_on_empty_target_gap_types(tmp_path: Path) -> None:
    pb = _make_minimal_playbook()
    pb["target_gap_types"] = []
    path = _write_playbooks(tmp_path, [pb])
    with pytest.raises(ValueError, match="empty target_gap_types"):
        load_playbooks(path)


def test_load_fails_on_empty_nvidia_technologies(tmp_path: Path) -> None:
    pb = _make_minimal_playbook()
    pb["nvidia_technologies"] = []
    path = _write_playbooks(tmp_path, [pb])
    with pytest.raises(ValueError, match="empty nvidia_technologies"):
        load_playbooks(path)


def test_load_fails_on_empty_success_metrics(tmp_path: Path) -> None:
    pb = _make_minimal_playbook()
    pb["success_metrics"] = []
    path = _write_playbooks(tmp_path, [pb])
    with pytest.raises(ValueError, match="empty success_metrics"):
        load_playbooks(path)


def test_load_fails_on_invalid_motion(tmp_path: Path) -> None:
    pb = _make_minimal_playbook()
    pb["recommended_motion"] = "invalid_motion"
    path = _write_playbooks(tmp_path, [pb])
    with pytest.raises(ValueError, match="invalid recommended_motion"):
        load_playbooks(path)


def test_load_fails_on_invalid_complexity(tmp_path: Path) -> None:
    pb = _make_minimal_playbook()
    pb["implementation_complexity"] = "extreme"
    path = _write_playbooks(tmp_path, [pb])
    with pytest.raises(ValueError, match="invalid implementation_complexity"):
        load_playbooks(path)


def test_load_fails_on_missing_version(tmp_path: Path) -> None:
    pb = _make_minimal_playbook()
    del pb["version"]
    path = _write_playbooks(tmp_path, [pb])
    with pytest.raises(ValueError, match="missing 'version'"):
        load_playbooks(path)


def test_default_playbook_path_has_10_playbooks() -> None:
    playbooks = load_playbooks()
    assert len(playbooks) == 10
    ids = {pb.playbook_id for pb in playbooks}
    expected = {
        "inference_cost_optimization",
        "latency_optimization",
        "agent_governance",
        "data_pipeline_acceleration",
        "computer_vision_acceleration",
        "voice_ai",
        "simulation_digital_twins",
        "robotics",
        "cybersecurity_ai",
        "private_controlled_deployment",
    }
    assert ids == expected
