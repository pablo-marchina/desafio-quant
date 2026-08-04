#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path

REQUIRED_SOURCES = {
    "StartSe",
    "Distrito",
    "Latitud",
    "Cubo Itau",
    "ACE Startups",
    "Endeavor Brasil",
    "Abstartups",
    "Bossa Invest",
    "Anjos do Brasil",
    "Darwin Startups",
    "Liga Ventures",
    "WOW Aceleradora",
    "InovAtiva Brasil",
    "100 Open Startups",
    "Brazil Journal",
    "NeoFeed",
    "Exame Startups",
    "Startups.com.br",
    "PEGN",
    "Valor Economico",
    "Meio & Mensagem",
    "Mobile Time",
}


def validate_source_coverage(path: Path) -> list[str]:
    if not path.exists():
        return [f"Missing source registry: {path}"]
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    names = {_normalize(row.get("source_name", "")) for row in rows}
    missing = sorted(source for source in REQUIRED_SOURCES if _normalize(source) not in names)
    failures = [f"Missing required source: {source}" for source in missing]
    for row in rows:
        url = row.get("source_url", "")
        if "example.com" in url and row.get("source_type") not in {"official_site", "official_blog", "careers"}:
            failures.append(f"Placeholder URL in active registry: {row.get('source_name')}")
    return failures


def _normalize(value: str) -> str:
    return (
        value.casefold()
        .replace("í", "i")
        .replace("ú", "u")
        .replace("ã", "a")
        .replace("ô", "o")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("á", "a")
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Check required Brazilian startup source coverage.")
    parser.add_argument("--registry", type=Path, default=Path("data/source_registry.csv"))
    args = parser.parse_args()
    failures = validate_source_coverage(args.registry)
    if failures:
        print("FAIL: source coverage")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print("PASS: source coverage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
