from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

from app.services.database_backup import create_backup


def main() -> None:
    parser = argparse.ArgumentParser(description="Cria backup do schema nvidia_inception.")
    parser.add_argument("--output-dir", type=Path, default=BACKEND_DIR / "data/backups")
    args = parser.parse_args()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL nao configurada")
    backup, manifest = create_backup(database_url, args.output_dir)
    print(f"Backup: {backup}")
    print(f"Manifest: {manifest}")


if __name__ == "__main__":
    main()
