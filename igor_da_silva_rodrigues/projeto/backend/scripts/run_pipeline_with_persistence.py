import json
import sys
from pathlib import Path


sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.persistence.pipeline_with_persistence import run_pipeline_with_persistence


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(
            'Uso: python scripts/run_pipeline_with_persistence.py "Nome Startup" [https://site.com]'
        )
    result = run_pipeline_with_persistence(
        {
            "startup_name": sys.argv[1],
            "site_oficial": sys.argv[2] if len(sys.argv) > 2 else None,
        }
    )
    sys.stdout.buffer.write(
        (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
