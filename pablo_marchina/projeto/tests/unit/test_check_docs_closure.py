from __future__ import annotations

import subprocess
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
CHECK_CLOSURE = SCRIPTS_DIR / "check_docs_closure.py"


def run_check_closure(args: list[str] | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess:
    cmd = ["python", str(CHECK_CLOSURE)]
    if cwd:
        cmd.extend(["--repo-path", str(cwd)])
    if args:
        cmd.extend(args)
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd or SCRIPTS_DIR.parent)


def test_check_closure_script_exists():
    assert CHECK_CLOSURE.is_file(), f"{CHECK_CLOSURE} not found"


def test_check_closure_runnable():
    result = run_check_closure()
    assert result.returncode in (0, 1)


def test_check_closure_with_explicit_plan(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "docs").mkdir()
    (repo / "docs" / "plans").mkdir(parents=True, exist_ok=True)
    plan = repo / "docs" / "plans" / "2026-06-10_epic-16_test-plan.md"
    plan.write_text("# Plan")
    (repo / "ROADMAP.md").write_text("# ROADMAP\n\n## Concluidos\n\n### Epic 16\n")
    (repo / "EVALS.md").write_text("# EVALS\n\n## CI/CD Quality Gates\n")
    (repo / "obsidian-vault").mkdir(parents=True, exist_ok=True)
    (repo / "obsidian-vault" / "04 Decisions").mkdir(parents=True, exist_ok=True)
    (repo / "obsidian-vault" / "04 Decisions" / "Epic 16 Decision.md").write_text("# Decision")
    (repo / "obsidian-vault" / "03 Research").mkdir(parents=True, exist_ok=True)
    (repo / "obsidian-vault" / "03 Research" / "Epic 16 Research.md").write_text("# Research")
    result = run_check_closure(["--plan", str(plan.relative_to(repo))], cwd=repo)
    assert result.returncode == 0
    assert "All closure checks passed" in result.stdout


def test_check_closure_missing_plan(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "docs").mkdir()
    (repo / "docs" / "plans").mkdir(parents=True, exist_ok=True)
    (repo / "ROADMAP.md").write_text("# ROADMAP\n\n## Concluidos\n\n### Epic 16\n")
    (repo / "EVALS.md").write_text("# EVALS\n\n## CI/CD Quality Gates\n")
    result = run_check_closure(cwd=repo)
    assert result.returncode == 1


def test_check_closure_missing_roadmap(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "docs").mkdir()
    (repo / "docs" / "plans").mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "plans" / "2026-06-10_epic-16_test-plan.md").write_text("# Plan")
    (repo / "EVALS.md").write_text("# EVALS\n\n## CI/CD Quality Gates\n")
    result = run_check_closure(cwd=repo)
    assert result.returncode == 1


def test_check_closure_missing_evals(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "docs").mkdir()
    (repo / "docs" / "plans").mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "plans" / "2026-06-10_epic-16_test-plan.md").write_text("# Plan")
    (repo / "ROADMAP.md").write_text("# ROADMAP\n\n## Concluidos\n\n### Epic 16\n")
    result = run_check_closure(cwd=repo)
    assert result.returncode == 1


def test_check_closure_no_roadmap_section_mixed(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "docs").mkdir()
    (repo / "docs" / "plans").mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "plans" / "2026-06-10_epic-16_test-plan.md").write_text("# Plan")
    (repo / "ROADMAP.md").write_text("# ROADMAP\n\nNo concluidos section\n")
    (repo / "EVALS.md").write_text("# EVALS\n\n## CI/CD Quality Gates\n")
    result = run_check_closure(cwd=repo)
    assert result.returncode == 1
