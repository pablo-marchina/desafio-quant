import json
import sys
from pathlib import Path


sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.scraping import coletar_startups_cubo


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    result = [startup.to_dict() for startup in coletar_startups_cubo(limit=limit)]
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    sys.stdout.buffer.write(payload.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
