from __future__ import annotations

import argparse
import sys
from pathlib import Path
from uuid import UUID

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.evaluation.batch_report import BatchAcceptanceReport
from app.persistence.batch_repository import BatchRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera relatorio de aceitacao do lote.")
    parser.add_argument("batch_id", type=UUID)
    parser.add_argument("--allow-incomplete", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("../docs/acceptance/lote_50_2026-06-28.md"),
    )
    args = parser.parse_args()
    path = BatchAcceptanceReport(BatchRepository.from_env()).generate(
        args.batch_id,
        args.output,
        allow_incomplete=args.allow_incomplete,
    )
    print(path.resolve())


if __name__ == "__main__":
    main()
