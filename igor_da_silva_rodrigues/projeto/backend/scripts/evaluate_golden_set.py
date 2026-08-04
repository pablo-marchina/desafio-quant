from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.evaluation.golden_set import load_golden_set
from app.evaluation.harness import SupabaseEvaluationLoader, evaluate_golden_set
from app.persistence.persistence_service import PipelinePersistence


def main() -> None:
    parser = argparse.ArgumentParser(description="Avalia o pipeline contra o conjunto ouro aprovado.")
    parser.add_argument(
        "--golden-set",
        type=Path,
        default=PROJECT_DIR / "docs/evaluation/golden_set_v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_DIR / "docs/evaluation/latest_report.json",
    )
    args = parser.parse_args()

    golden_set = load_golden_set(args.golden_set)
    try:
        golden_set.require_approved()
    except ValueError as exc:
        print(f"Avaliacao nao executada: {exc}", file=sys.stderr)
        raise SystemExit(3) from None
    loader = SupabaseEvaluationLoader(PipelinePersistence.from_env())
    actual = {case.case_id: loader.load(case) for case in golden_set.cases}
    report = evaluate_golden_set(golden_set, actual)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["overall_passed"] else 2)


if __name__ == "__main__":
    main()
