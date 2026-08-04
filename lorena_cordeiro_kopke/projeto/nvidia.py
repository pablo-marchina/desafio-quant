from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable


def main() -> None:
    print("=" * 60)
    print("  NVIDIA · Radar de Startups")
    print("=" * 60)
    print("\nAbrindo dashboard (use a página 'Pipeline' para executar a coleta)...\n")
    subprocess.run([PYTHON, "-m", "streamlit", "run", str(ROOT / "dashboard.py")])


if __name__ == "__main__":
    main()
