from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.persistence.persistence_service import PipelinePersistence
from app.services.retention_service import RetentionService


def main() -> None:
    parser = argparse.ArgumentParser(description="Aplica a politica de retencao do backend.")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Remove os dados listados. Sem esta flag, executa apenas dry-run.",
    )
    args = parser.parse_args()
    service = RetentionService(persistence=PipelinePersistence.from_env())
    report = service.run(execute=args.execute)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
