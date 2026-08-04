from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_step(label: str, command: list[str]) -> bool:
    print(f"\n== {label} ==", flush=True)
    print(" ".join(command), flush=True)
    completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    if completed.returncode == 0:
        print(f"[ok] {label}", flush=True)
        return True
    print(f"[fail] {label}: exit code {completed.returncode}", flush=True)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Valida o MVP local com checks offline e smoke opcional."
    )
    parser.add_argument(
        "--with-smoke",
        action="store_true",
        help="Tambem roda scripts/smoke_rag.py; requer API, Qdrant e Postgres ativos.",
    )
    parser.add_argument(
        "--with-rag-eval",
        action="store_true",
        help="Tambem roda scripts/evaluate_rag.py; requer API e base NVIDIA ingerida.",
    )
    args = parser.parse_args()

    steps: list[tuple[str, list[str]]] = [
        (
            "Python unit/API tests",
            [sys.executable, "-m", "unittest", "discover", "-s", "apps/api/tests"],
        ),
    ]

    node = shutil.which("node")
    if node:
        steps.append(("Static JS syntax", [node, "--check", "apps/api/app/static/app.js"]))
    else:
        print("[skip] Static JS syntax: node nao encontrado no PATH.", flush=True)

    steps.append(("Git whitespace check", ["git", "diff", "--check"]))

    if args.with_smoke:
        steps.append(("RAG/API smoke test", [sys.executable, "scripts/smoke_rag.py"]))
    if args.with_rag_eval:
        steps.append(("RAG 15-question evaluation", [sys.executable, "scripts/evaluate_rag.py"]))

    failed = False
    for label, command in steps:
        if not run_step(label, command):
            failed = True

    if failed:
        print("\nValidacao do MVP falhou.", flush=True)
        return 1

    print("\nValidacao do MVP concluida com sucesso.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
