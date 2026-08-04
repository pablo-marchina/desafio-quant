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

from app.services.database_backup import restore_backup, verify_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Restaura backup em banco isolado.")
    parser.add_argument("backup", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--confirm-isolated-target", action="store_true")
    args = parser.parse_args()
    if not args.confirm_isolated_target:
        raise SystemExit("Use --confirm-isolated-target para confirmar o destino de teste")
    source = os.getenv("DATABASE_URL")
    target = os.getenv("RESTORE_DATABASE_URL")
    if not source or not target:
        raise SystemExit("DATABASE_URL e RESTORE_DATABASE_URL sao obrigatorias")
    if not verify_manifest(args.backup, args.manifest):
        raise SystemExit("Checksum do backup nao confere")
    restore_backup(args.backup, target, source)
    print("Restauracao concluida no destino isolado.")


if __name__ == "__main__":
    main()
