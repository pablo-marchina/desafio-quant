from __future__ import annotations

from pathlib import Path

from src.playbook.schemas import ActivationPlaybook

_DEFAULT_PLAYBOOK_PATH = (
    Path(__file__).resolve().parent.parent / "config" / "playbooks" / "nvidia_activation_playbooks.yaml"
)


def load_playbooks(path: Path | str | None = None) -> list[ActivationPlaybook]:
    resolved = Path(path).expanduser().resolve() if path else _DEFAULT_PLAYBOOK_PATH

    import yaml

    raw = resolved.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if not isinstance(data, dict) or "playbooks" not in data:
        raise ValueError(f"Playbook file {resolved} must contain a top-level 'playbooks' key")

    playbooks_raw: list[dict] = data["playbooks"]
    if not playbooks_raw:
        raise ValueError(f"Playbook file {resolved} contains no playbooks")

    playbooks: list[ActivationPlaybook] = []
    seen_ids: set[str] = set()
    for i, pb in enumerate(playbooks_raw):
        _validate_playbook_dict(pb, resolved, i)
        pid = pb["playbook_id"]
        if pid in seen_ids:
            raise ValueError(f"Duplicate playbook_id '{pid}' in {resolved} at index {i}")
        seen_ids.add(pid)
        playbooks.append(ActivationPlaybook(**pb))

    return playbooks


_VALID_MOTIONS = {
    "technical_workshop",
    "immediate_outreach",
    "monitor_and_nurture",
    "lack_evidence_more_research",
    "not_recommended",
}

_VALID_COMPLEXITIES = {"low", "medium", "high"}


def _validate_playbook_dict(pb: dict, path: Path, index: int) -> None:
    if not pb.get("playbook_id"):
        raise ValueError(f"Playbook at index {index} in {path} is missing 'playbook_id'")
    if not pb.get("target_gap_types"):
        raise ValueError(f"Playbook '{pb.get('playbook_id', '?')}' in {path} has empty target_gap_types")
    if not pb.get("nvidia_technologies"):
        raise ValueError(f"Playbook '{pb.get('playbook_id', '?')}' in {path} has empty nvidia_technologies")
    if not pb.get("success_metrics"):
        raise ValueError(f"Playbook '{pb.get('playbook_id', '?')}' in {path} has empty success_metrics")
    motion = pb.get("recommended_motion", "")
    if motion not in _VALID_MOTIONS:
        raise ValueError(
            f"Playbook '{pb.get('playbook_id', '?')}' in {path} "
            f"has invalid recommended_motion '{motion}'. "
            f"Must be one of {sorted(_VALID_MOTIONS)}"
        )
    complexity = pb.get("implementation_complexity", "")
    if complexity not in _VALID_COMPLEXITIES:
        raise ValueError(
            f"Playbook '{pb.get('playbook_id', '?')}' in {path} "
            f"has invalid implementation_complexity '{complexity}'. "
            f"Must be one of {sorted(_VALID_COMPLEXITIES)}"
        )
    if not pb.get("version"):
        raise ValueError(f"Playbook '{pb.get('playbook_id', '?')}' in {path} is missing 'version'")
