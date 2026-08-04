import sys
from pathlib import Path


sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.processing import validar_arquivo_prosseguir


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Uso: python scripts/validar_prosseguir.py caminho/arquivo.json")

    relatorio = validar_arquivo_prosseguir(Path(sys.argv[1]))
    sys.stdout.buffer.write(relatorio.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
