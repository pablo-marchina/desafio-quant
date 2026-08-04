from __future__ import annotations

import csv
from pathlib import Path

LEDGER_COLUMNS = [
    "decision_id",
    "area",
    "decision",
    "alternatives_considered",
    "metrics_used",
    "data_source",
    "benchmark_file",
    "chosen_option",
    "expected_value",
    "confidence",
    "uncertainty",
    "risks",
    "owner",
    "date",
    "status",
]


def append_decision(path: Path, row: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_COLUMNS)
        if not exists:
            writer.writeheader()
        writer.writerow({column: row.get(column, "") for column in LEDGER_COLUMNS})
