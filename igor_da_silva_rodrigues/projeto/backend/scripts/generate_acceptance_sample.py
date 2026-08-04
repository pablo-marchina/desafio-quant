from __future__ import annotations

import argparse
import sys
from pathlib import Path
from uuid import UUID


sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.evaluation.acceptance import AcceptanceSampleGenerator
from app.persistence.batch_repository import BatchRepository


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera amostra de revisao do lote.")
    parser.add_argument("batch_id", type=UUID)
    parser.add_argument("--size", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260627)
    parser.add_argument("--allow-incomplete", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("../docs/acceptance/revisao_amostra_10.csv"),
    )
    args = parser.parse_args()
    path = AcceptanceSampleGenerator(BatchRepository.from_env()).generate(
        args.batch_id,
        output_path=args.output,
        sample_size=args.size,
        seed=args.seed,
        allow_incomplete=args.allow_incomplete,
    )
    print(path.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
