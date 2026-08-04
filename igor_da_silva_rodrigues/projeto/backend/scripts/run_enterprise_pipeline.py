import json
import sys
from pathlib import Path


sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.enterprise_pipeline import run_enterprise_pipeline


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(
            'Uso: python scripts/run_enterprise_pipeline.py "Nome Startup" [https://site.com]'
        )
    payload = {
        "startup_name": sys.argv[1],
        "site_oficial": sys.argv[2] if len(sys.argv) > 2 else None,
    }
    result = run_enterprise_pipeline(payload)
    sys.stdout.buffer.write(
        (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
