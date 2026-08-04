from __future__ import annotations

import importlib
import os
import pkgutil
import re
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"

SOURCE_TEXT_EXTENSIONS = {
    ".md",
    ".py",
    ".txt",
    ".ini",
    ".yml",
    ".yaml",
}

CLI_MODULES_WITH_HELP = (
    "agents.nvidia.graph",
    "rag.evaluation.ragas_eval",
    "rag.generation.rag_query",
    "rag.retrieval.search",
    "rag.scraping.catalog_scraper",
    "scraper.enrichment_pipeline.catalog_correction",
    "scraper.enrichment_pipeline.main",
    "scraper.rss_news.main",
    "scraper.startupbase_api.main",
    "scraper.validation_pipeline.cleanup_main",
    "scraper.validation_pipeline.main",
)


def _source_files() -> list[Path]:
    roots = [
        PROJECT_ROOT / ".github",
        PROJECT_ROOT / "requirements",
        PROJECT_ROOT / "scripts",
        PROJECT_ROOT / "src",
        PROJECT_ROOT / "tests",
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "compose.yaml",
        PROJECT_ROOT / "pytest.ini",
    ]
    files: list[Path] = []
    for root in roots:
        if root.is_file():
            files.append(root)
            continue
        files.extend(
            path
            for path in root.rglob("*")
            if path.is_file() and path.suffix in SOURCE_TEXT_EXTENSIONS
        )
    return files


def _subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        f"{SRC_ROOT}{os.pathsep}{existing_pythonpath}"
        if existing_pythonpath
        else str(SRC_ROOT)
    )
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def test_all_src_modules_are_importable() -> None:
    modules: list[str] = []
    for package_name in ("agents", "rag", "scraper", "shared"):
        package = importlib.import_module(package_name)
        modules.extend(
            module.name
            for module in pkgutil.walk_packages(
                package.__path__, prefix=f"{package_name}."
            )
        )
    modules = sorted(modules)

    assert modules, "Nenhum modulo encontrado em src"

    failures: dict[str, str] = {}
    for module_name in modules:
        try:
            importlib.import_module(module_name)
        except Exception as error:  # pragma: no cover - diagnostic branch
            failures[module_name] = repr(error)

    assert failures == {}


def test_cli_entrypoints_expose_help_without_runtime_side_effects() -> None:
    for module_name in CLI_MODULES_WITH_HELP:
        completed = subprocess.run(
            [sys.executable, "-m", module_name, "--help"],
            cwd=PROJECT_ROOT,
            env=_subprocess_env(),
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
        )
        assert completed.returncode == 0, (
            module_name,
            completed.stdout,
            completed.stderr,
        )
        assert "usage:" in completed.stdout.lower()


def test_script_entrypoints_expose_help_without_runtime_side_effects() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/run_scheduled_scan.py", "--help"],
        cwd=PROJECT_ROOT,
        env=_subprocess_env(),
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, (completed.stdout, completed.stderr)
    assert "usage:" in completed.stdout.lower()


def test_fastapi_application_is_exposed() -> None:
    module = importlib.import_module("scraper.api.main")

    assert module.app.title == "Startup AI Radar API"


def test_project_no_longer_references_legacy_package_paths() -> None:
    forbidden_patterns = (
        (re.compile(r"\b(?:from|import)\s+startup_scraper\b"), "old startup_scraper import"),
        (re.compile(r"\bstartup_scraper[./]"), "old startup_scraper path"),
        (re.compile(r"\bpython\s+-m\s+startup_scraper\b"), "old startup_scraper CLI"),
        (re.compile(r"\b(?:from|import)\s+nvidia_rag\b"), "old nvidia_rag import"),
        (re.compile(r"\bnvidia_rag[./]"), "old nvidia_rag path"),
        (re.compile(r"\bpython\s+-m\s+nvidia_rag\b"), "old nvidia_rag CLI"),
        (re.compile(r"\bdicionario\.py\b"), "old root catalog filename"),
        (re.compile(r"\brequirements/rag\.txt\b"), "old RAG requirements filename"),
        (re.compile(r"\.venv-scraping\b"), "old scraping venv"),
        (re.compile(r"\.venv-embedding\b"), "old embedding venv"),
        (re.compile(r"\b_legacy_supabase_service\b"), "removed legacy Supabase service"),
        (re.compile(r"\bidentity_validation\.py\b"), "removed identity validation module"),
    )

    violations: list[str] = []
    for path in _source_files():
        if path.name == "test_project_integrity.py":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern, description in forbidden_patterns:
            if pattern.search(text):
                relative = path.relative_to(PROJECT_ROOT)
                violations.append(f"{relative}: {description}")

    assert violations == []


def test_generated_and_local_environment_files_are_not_tracked() -> None:
    completed = subprocess.run(
        ["git", "ls-files"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    tracked = completed.stdout.splitlines()

    forbidden_tracked = [
        path
        for path in tracked
        if (
            "__pycache__" in path
            or path.endswith(".pyc")
            or path.startswith(".venv")
            or path.startswith(".agents/")
            or path.startswith(".codex-plugins/")
            or path == ".env"
        )
    ]

    assert forbidden_tracked == []


def test_gitignore_protects_generated_and_local_environment_files() -> None:
    gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")

    for pattern in (
        ".env",
        ".venv/",
        ".venv-*/",
        "__pycache__/",
        "*.py[cod]",
        ".agents/",
        ".codex-plugins/",
    ):
        assert pattern in gitignore
