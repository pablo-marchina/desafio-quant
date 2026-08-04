import json
import sys
from pathlib import Path


sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.processing import construir_curated_cubo


if __name__ == "__main__":
    resultado = construir_curated_cubo()
    payload = json.dumps(resultado, ensure_ascii=False, indent=2)
    sys.stdout.buffer.write(payload.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
