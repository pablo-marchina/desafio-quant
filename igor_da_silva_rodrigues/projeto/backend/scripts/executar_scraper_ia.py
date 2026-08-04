import json
import sys
from pathlib import Path


sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.agents.scraper_agent import executar_scraper_agent, salvar_resultado_scraper


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Uso: python scripts/executar_scraper_ia.py caminho/plano.json")

    input_path = Path(sys.argv[1])
    plano = json.loads(input_path.read_text(encoding="utf-8"))
    resultado = executar_scraper_agent(plano)
    output_path = salvar_resultado_scraper(resultado)

    payload = json.dumps(
        {
            "arquivo_saida": str(output_path),
            **resultado,
        },
        ensure_ascii=False,
        indent=2,
    )
    sys.stdout.buffer.write(payload.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
