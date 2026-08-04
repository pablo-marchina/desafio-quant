import json
import sys
from pathlib import Path


sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.ai_evidence_pipeline import executar_pipeline_investigacao_ia


def _selecionar_startup(startups, startup_ref):
    needle = startup_ref.lower()
    for startup in startups:
        if startup.get("startup_id", "").lower() == needle:
            return startup
        if startup.get("nome", "").lower() == needle:
            return startup
    return None


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit(
            "Uso: python scripts/investigar_startup_ia.py caminho/curated.json \"Nome ou startup_id\""
        )

    curated_path = Path(sys.argv[1])
    startup_ref = sys.argv[2]
    payload = json.loads(curated_path.read_text(encoding="utf-8"))
    startup = _selecionar_startup(payload.get("startups", []), startup_ref)
    if not startup:
        raise SystemExit(f"Startup não encontrada: {startup_ref}")

    resultado = executar_pipeline_investigacao_ia(startup)

    payload = json.dumps(resultado, ensure_ascii=False, indent=2)
    sys.stdout.buffer.write(payload.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
