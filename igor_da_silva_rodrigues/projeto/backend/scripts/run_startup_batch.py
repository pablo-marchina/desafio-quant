from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import UUID


sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.batch_processing_service import BatchExecutionOptions, BatchProcessingService


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Processa a base CURATED em lotes duraveis.")
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create", help="Cria um lote a partir da base CURATED.")
    create.add_argument("--source", help="Nome do JSON dentro de data/curated/_cubo.")
    create.add_argument("--limit", type=int, choices=range(1, 51))
    create.add_argument("--startup-id", action="append", dest="startup_ids", default=[])
    create.add_argument("--eligible-only", action="store_true")
    create.add_argument("--max-attempts", type=int, choices=range(1, 4), default=2)
    create.add_argument("--stop-on-error", action="store_true")
    create.add_argument("--run", action="store_true", help="Executa imediatamente apos criar.")

    for name in ("run", "resume", "status", "cancel"):
        command = commands.add_parser(name)
        command.add_argument("batch_id", type=UUID)
    return parser


def main() -> int:
    args = _parser().parse_args()
    service = BatchProcessingService.from_env()
    if args.command == "create":
        options = BatchExecutionOptions(
            limit=args.limit,
            startup_ids=args.startup_ids,
            include_ineligible=not args.eligible_only,
            max_attempts=args.max_attempts,
            stop_on_error=args.stop_on_error,
        )
        batch_id = service.create_batch(args.source, options)
        result = service.run_batch(batch_id) if args.run else service.repository.get_batch(batch_id)
    elif args.command == "run":
        result = service.run_batch(args.batch_id)
    elif args.command == "resume":
        result = service.run_batch(args.batch_id, resume=True)
    elif args.command == "cancel":
        service.repository.cancel_batch(args.batch_id)
        result = service.repository.get_batch(args.batch_id)
    else:
        result = {
            "batch": service.repository.get_batch(args.batch_id),
            "items": service.repository.list_items(args.batch_id),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
