from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import UUID


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.evaluation.quality_audit import BatchQualityAudit, render_quality_report
from app.persistence.batch_repository import BatchRepository


def main() -> int:
    parser = argparse.ArgumentParser(description="Audita a qualidade persistida de um lote.")
    parser.add_argument("batch_id", type=UUID)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_DIR / "docs" / "acceptance",
    )
    parser.add_argument(
        "--golden-set",
        type=Path,
        default=PROJECT_DIR / "docs" / "evaluation" / "golden_set_v1.json",
    )
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--retry-delay", type=float, default=2.0)
    args = parser.parse_args()

    audit = _with_retry(
        lambda: BatchQualityAudit(BatchRepository.from_env()).run(args.batch_id),
        attempts=args.attempts,
        retry_delay=args.retry_delay,
    )
    human_status = _golden_set_status(args.golden_set)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"auditoria_qualidade_{args.batch_id}"
    json_path = args.output_dir / f"{stem}.json"
    markdown_path = args.output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_quality_report(audit, human_status), encoding="utf-8")
    print(markdown_path)
    return 0 if audit["automatic_status"] == "approved" else 1


def _golden_set_status(path: Path) -> str:
    if not path.is_file():
        return "missing"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return str(payload.get("status") or "unknown")


def _with_retry(
    operation: Callable[[], dict[str, Any]],
    attempts: int,
    retry_delay: float,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    if attempts < 1:
        raise ValueError("attempts deve ser pelo menos 1")
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except Exception as exc:
            if attempt == attempts:
                raise
            print(
                f"Tentativa {attempt}/{attempts} falhou: {exc}. Nova tentativa sera executada.",
                file=sys.stderr,
            )
            sleep(retry_delay * attempt)
    raise RuntimeError("Auditoria terminou sem resultado")


if __name__ == "__main__":
    raise SystemExit(main())
