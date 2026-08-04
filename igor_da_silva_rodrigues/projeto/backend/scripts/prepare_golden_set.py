from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.evaluation.golden_set import GoldenCase, GoldenSet, save_golden_set


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepara um conjunto ouro draft a partir da amostra de aceitacao."
    )
    parser.add_argument("sample_csv", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_DIR / "docs/evaluation/golden_set_v1.json",
    )
    args = parser.parse_args()

    rows = _read_sample(args.sample_csv)
    if len(rows) < 10:
        raise SystemExit(f"A amostra precisa conter 10 casos; encontrados: {len(rows)}")
    batch_ids = {row["batch_id"] for row in rows}
    if len(batch_ids) != 1:
        raise SystemExit("A amostra deve pertencer a um unico lote")

    cases = [
        GoldenCase(
            case_id=f"{index:02d}-{_slug(row['startup_name'])}",
            startup=row["startup_name"],
            pipeline_run_id=UUID(row["pipeline_run_id"]),
        )
        for index, row in enumerate(rows[:10], start=1)
    ]
    golden_set = GoldenSet(
        version="1.0.0-draft",
        status="draft",
        created_at=datetime.now(UTC),
        description="Amostra independente para rotulagem e aprovacao humana.",
        source_batch_id=UUID(next(iter(batch_ids))),
        code_commit=_git_commit(),
        cases=cases,
    )
    save_golden_set(golden_set, args.output)
    print(f"Conjunto ouro draft salvo em {args.output} com {len(cases)} casos.")


def _read_sample(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    required = {"batch_id", "pipeline_run_id", "startup_name"}
    if not rows or not required.issubset(rows[0]):
        raise SystemExit(f"CSV invalido; colunas obrigatorias: {', '.join(sorted(required))}")
    return rows


def _git_commit() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _slug(value: str) -> str:
    return "-".join("".join(character.lower() if character.isalnum() else " " for character in value).split())


if __name__ == "__main__":
    main()
