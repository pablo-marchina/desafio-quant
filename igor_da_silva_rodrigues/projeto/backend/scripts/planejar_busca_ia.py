import json
import sys
from pathlib import Path


sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.agents.search_planner_agent import planejar_busca_ia_arquivo_curated


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit(
            "Uso: python scripts/planejar_busca_ia.py caminho/curated.json \"Nome ou startup_id\""
        )

    plano = planejar_busca_ia_arquivo_curated(Path(sys.argv[1]), sys.argv[2])
    payload = json.dumps(plano, ensure_ascii=False, indent=2)
    sys.stdout.buffer.write(payload.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
