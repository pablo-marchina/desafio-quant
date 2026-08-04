from __future__ import annotations

import subprocess
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
CHECK_SCOPE = SCRIPTS_DIR / "check_scope.py"


def run_check_scope(args: list[str] | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess:
    cmd = ["python", str(CHECK_SCOPE)]
    if cwd:
        cmd.extend(["--repo-path", str(cwd)])
    if args:
        cmd.extend(args)
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd or SCRIPTS_DIR.parent)


def test_check_scope_script_exists():
    assert CHECK_SCOPE.is_file(), f"{CHECK_SCOPE} not found"


def test_check_scope_runnable():
    result = run_check_scope()
    assert result.returncode in (0, 1)
    assert "Changed files" in result.stdout or "No changes detected" in result.stdout


def test_check_scope_no_changes_ok(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    result = subprocess.run(
        ["git", "init"],
        capture_output=True,
        text=True,
        cwd=repo,
        check=True,
    )
    result = subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        capture_output=True,
        text=True,
        cwd=repo,
        check=True,
    )
    result = subprocess.run(
        ["git", "config", "user.name", "Test"],
        capture_output=True,
        text=True,
        cwd=repo,
        check=True,
    )
    (repo / "README.md").write_text("# Test")
    result = subprocess.run(
        ["git", "add", "."],
        capture_output=True,
        text=True,
        cwd=repo,
        check=True,
    )
    result = subprocess.run(
        ["git", "commit", "-m", "init"],
        capture_output=True,
        text=True,
        cwd=repo,
        check=True,
    )
    result = run_check_scope(cwd=repo)
    assert "No changes detected" in result.stdout
    assert result.returncode == 0


def test_check_scope_requires_evals_when_src_changes(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], capture_output=True, text=True, cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        capture_output=True,
        text=True,
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Test"], capture_output=True, text=True, cwd=repo, check=True)
    (repo / "README.md").write_text("# Test")
    subprocess.run(["git", "add", "."], capture_output=True, text=True, cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], capture_output=True, text=True, cwd=repo, check=True)
    (repo / "src" / "pipeline" / "test.txt").parent.mkdir(parents=True, exist_ok=True)
    (repo / "src" / "pipeline" / "test.txt").write_text("change")
    result = run_check_scope(cwd=repo)
    assert result.returncode == 1
    assert "ROADMAP.md" in result.stdout
    assert "EVALS.md" in result.stdout


def test_check_scope_override_flag(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], capture_output=True, text=True, cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        capture_output=True,
        text=True,
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Test"], capture_output=True, text=True, cwd=repo, check=True)
    (repo / "README.md").write_text("# Test")
    subprocess.run(["git", "add", "."], capture_output=True, text=True, cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], capture_output=True, text=True, cwd=repo, check=True)
    (repo / "src" / "rag" / "test.txt").parent.mkdir(parents=True, exist_ok=True)
    (repo / "src" / "rag" / "test.txt").write_text("rag change")
    result = run_check_scope(cwd=repo)
    assert result.returncode == 1
    result = run_check_scope(
        [
            "--override",
            "ROADMAP.md",
            "--override",
            "EVALS.md",
            "--override",
            "docs/contracts/rag_contract.md",
        ],
        cwd=repo,
    )
    assert result.returncode == 0


def test_check_scope_contract_required_for_src_rag(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], capture_output=True, text=True, cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        capture_output=True,
        text=True,
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Test"], capture_output=True, text=True, cwd=repo, check=True)
    (repo / "README.md").write_text("# Test")
    subprocess.run(["git", "add", "."], capture_output=True, text=True, cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], capture_output=True, text=True, cwd=repo, check=True)
    (repo / "src" / "rag" / "test.txt").parent.mkdir(parents=True, exist_ok=True)
    (repo / "src" / "rag" / "test.txt").write_text("rag change")
    (repo / "ROADMAP.md").write_text("# ROADMAP")
    (repo / "EVALS.md").write_text("# EVALS")
    result = run_check_scope(cwd=repo)
    assert result.returncode == 1
    assert "rag_contract.md" in result.stdout


def test_check_scope_contract_override(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], capture_output=True, text=True, cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        capture_output=True,
        text=True,
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Test"], capture_output=True, text=True, cwd=repo, check=True)
    (repo / "README.md").write_text("# Test")
    subprocess.run(["git", "add", "."], capture_output=True, text=True, cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], capture_output=True, text=True, cwd=repo, check=True)
    (repo / "src" / "rag" / "test.txt").parent.mkdir(parents=True, exist_ok=True)
    (repo / "src" / "rag" / "test.txt").write_text("rag change")
    (repo / "ROADMAP.md").write_text("# ROADMAP")
    (repo / "EVALS.md").write_text("# EVALS")
    (repo / "docs" / "contracts").mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "contracts" / "rag_contract.md").write_text("# RAG Contract")
    result = run_check_scope(cwd=repo)
    assert result.returncode == 0
