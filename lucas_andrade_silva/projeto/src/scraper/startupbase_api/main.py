from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import config
from .client import StartupBaseClient


def run(batch_size: int = 250, output: Path | None = None, dry_run: bool = False) -> int:
    client = StartupBaseClient()
    rows = list(client.iter_startups())
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    if not dry_run:
        from .database import connect, ensure_schema, upsert_startups

        with connect() as connection:
            ensure_schema(connection)
            for start in range(0, len(rows), batch_size):
                upsert_startups(rows[start:start + batch_size], connection)
    print(f"Concluido: {len(rows)} startups normalizadas" + (" (sem gravar no banco)" if dry_run else " e enviadas ao Supabase"))
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Coleta a API interna do StartupBase")
    parser.add_argument("--batch-size", type=int, default=250)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--portal-url", help="URL da listagem para descobrir a API via Playwright")
    source.add_argument("--api-url", help="Endpoint da API, quando ja conhecido")
    parser.add_argument("--api-method", choices=("GET", "POST"), help="Metodo do endpoint; padrao: valor do .env ou GET")
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size deve ser positivo")
    if args.portal_url:
        config.PORTAL_URL = args.portal_url
        config.API_URL = ""
    if args.api_url:
        config.API_URL = args.api_url
    if args.api_method:
        config.API_METHOD = args.api_method
    if not config.PORTAL_URL and not config.API_URL:
        parser.error(
            "informe --portal-url URL para descobrir a API ou --api-url URL para usar um endpoint conhecido; "
            "as mesmas opcoes podem ser definidas por STARTUPBASE_PORTAL_URL/STARTUPBASE_API_URL no .env"
        )
    run(args.batch_size, args.output, args.dry_run)


if __name__ == "__main__":
    main()
