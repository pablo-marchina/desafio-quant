from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.classification.ai_native_model import MODEL_PATH, load_jsonl, save_model, train_token_model


def main() -> int:
    parser = argparse.ArgumentParser(description="Train the local AI-native classifier from JSONL labels.")
    parser.add_argument(
        "--dataset",
        default="data/eval/ai_native_labeled_ptbr.jsonl",
        help="Path to JSONL records with label, text fields, and label_source.",
    )
    parser.add_argument("--output", default=str(MODEL_PATH), help="Output model JSON path.")
    args = parser.parse_args()

    records = load_jsonl(Path(args.dataset))
    model = train_token_model(records)
    save_model(model, Path(args.output))
    print(json.dumps({
        "status": "trained",
        "dataset": args.dataset,
        "output": args.output,
        "record_count": model["record_count"],
        "labels": model["labels"],
        "model_version": model["model_version"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
