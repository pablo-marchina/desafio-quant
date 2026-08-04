from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import requests


REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.config import get_settings
from app.startup_discovery import (
    discovery_adapter_for_url,
    parse_discovery_source_urls,
    source_label_from_url,
    startup_name_key,
)

DEFAULT_QUALITY_THRESHOLDS = {
    "min_total": 1,
    "min_valid_ratio": 0.75,
    "max_duplicate_ratio": 0.25,
    "max_unknown_sector_ratio": 0.6,
    "min_average_confidence": 55.0,
}


def evaluate_source_quality(
    *,
    error: str | None,
    total: int,
    valid_names: int,
    duplicate_names: int,
    unknown_sector: int,
    average_confidence: float,
    thresholds: dict[str, float | int] | None = None,
) -> tuple[str, list[str]]:
    rules = {**DEFAULT_QUALITY_THRESHOLDS, **(thresholds or {})}
    reasons: list[str] = []
    failing = False

    if error:
        return "fail", [f"erro de coleta: {error}"]

    if total < int(rules["min_total"]):
        return "fail", [f"nenhuma descoberta encontrada (minimo {rules['min_total']})"]

    valid_ratio = valid_names / total if total else 0.0
    duplicate_ratio = duplicate_names / valid_names if valid_names else 0.0
    unknown_sector_ratio = unknown_sector / total if total else 0.0

    if valid_names == 0:
        failing = True
        reasons.append("nenhum nome valido extraido")
    elif valid_ratio < float(rules["min_valid_ratio"]):
        reasons.append(
            "taxa de nomes validos abaixo do esperado "
            f"({valid_ratio:.2f} < {float(rules['min_valid_ratio']):.2f})"
        )

    if duplicate_ratio > float(rules["max_duplicate_ratio"]):
        reasons.append(
            "duplicacao acima do esperado "
            f"({duplicate_ratio:.2f} > {float(rules['max_duplicate_ratio']):.2f})"
        )

    if unknown_sector_ratio > float(rules["max_unknown_sector_ratio"]):
        reasons.append(
            "muitos setores desconhecidos "
            f"({unknown_sector_ratio:.2f} > {float(rules['max_unknown_sector_ratio']):.2f})"
        )

    if average_confidence < float(rules["min_average_confidence"]):
        reasons.append(
            "confianca media baixa "
            f"({average_confidence:.1f} < {float(rules['min_average_confidence']):.1f})"
        )

    if failing:
        return "fail", reasons
    if reasons:
        return "warn", reasons
    return "pass", []


def summarize_source_result(
    *,
    source_url: str,
    adapter_name: str,
    discoveries: list[dict[str, object]],
    error: str | None = None,
) -> dict[str, Any]:
    confidence_values = [
        int(item.get("confidence") or 0)
        for item in discoveries
        if item.get("confidence") is not None
    ]
    names = [startup_name_key(item.get("startup_name")) for item in discoveries]
    valid_names = [name for name in names if name]
    sectors = Counter(str(item.get("sector") or "unknown") for item in discoveries)
    total = len(discoveries)
    duplicate_names = len(valid_names) - len(set(valid_names))
    unknown_sector = sectors.get("unknown", 0)
    average_confidence = (
        round(sum(confidence_values) / len(confidence_values), 1)
        if confidence_values
        else 0.0
    )
    valid_name_ratio = round(len(valid_names) / total, 3) if total else 0.0
    duplicate_ratio = (
        round(duplicate_names / len(valid_names), 3) if valid_names else 0.0
    )
    unknown_sector_ratio = round(unknown_sector / total, 3) if total else 0.0
    quality_status, quality_reasons = evaluate_source_quality(
        error=error,
        total=total,
        valid_names=len(valid_names),
        duplicate_names=duplicate_names,
        unknown_sector=unknown_sector,
        average_confidence=average_confidence,
    )

    return {
        "source_url": source_url,
        "source_label": source_label_from_url(source_url),
        "adapter": adapter_name,
        "status": "error" if error else "ok",
        "error": error,
        "quality_status": quality_status,
        "quality_reasons": quality_reasons,
        "total": total,
        "valid_names": len(valid_names),
        "valid_name_ratio": valid_name_ratio,
        "duplicate_names": duplicate_names,
        "duplicate_ratio": duplicate_ratio,
        "unknown_sector": unknown_sector,
        "unknown_sector_ratio": unknown_sector_ratio,
        "average_confidence": average_confidence,
        "sectors": dict(sorted(sectors.items())),
        "examples": [
            {
                "startup_name": item.get("startup_name"),
                "sector": item.get("sector"),
                "confidence": item.get("confidence"),
                "title": item.get("article_title") or item.get("description"),
                "url": item.get("article_url") or item.get("source_url"),
            }
            for item in discoveries[:5]
        ],
    }


def check_source(source_url: str, max_items: int) -> dict[str, Any]:
    adapter = discovery_adapter_for_url(source_url)
    try:
        discoveries = adapter.collect(max_items=max_items)
    except requests.RequestException as error:
        return summarize_source_result(
            source_url=source_url,
            adapter_name=adapter.__class__.__name__,
            discoveries=[],
            error=str(error),
        )

    return summarize_source_result(
        source_url=source_url,
        adapter_name=adapter.__class__.__name__,
        discoveries=discoveries,
    )


def check_sources(source_urls: list[str], max_items: int) -> dict[str, Any]:
    sources = [check_source(source_url, max_items=max_items) for source_url in source_urls]
    return {
        "source_count": len(sources),
        "total_discoveries": sum(int(source["total"]) for source in sources),
        "ok_sources": sum(1 for source in sources if source["status"] == "ok"),
        "error_sources": sum(1 for source in sources if source["status"] == "error"),
        "quality_pass_sources": sum(
            1 for source in sources if source["quality_status"] == "pass"
        ),
        "quality_warn_sources": sum(
            1 for source in sources if source["quality_status"] == "warn"
        ),
        "quality_fail_sources": sum(
            1 for source in sources if source["quality_status"] == "fail"
        ),
        "sources": sources,
    }


def print_text_report(report: dict[str, Any]) -> None:
    print(
        "Startup source check: "
        f"{report['ok_sources']}/{report['source_count']} fontes OK, "
        f"{report['total_discoveries']} descobertas, "
        f"qualidade pass/warn/fail="
        f"{report['quality_pass_sources']}/"
        f"{report['quality_warn_sources']}/"
        f"{report['quality_fail_sources']}."
    )
    for source in report["sources"]:
        print("")
        print(
            f"[{source['quality_status']}] {source['source_label']} - "
            f"{source['source_url']} (coleta={source['status']})"
        )
        print(f"  adapter: {source['adapter']}")
        if source["error"]:
            print(f"  erro: {source['error']}")
            continue
        if source["quality_reasons"]:
            print(f"  alertas: {'; '.join(source['quality_reasons'])}")
        print(
            "  resultados: "
            f"total={source['total']} "
            f"nomes_validos={source['valid_names']} "
            f"ratio_validos={source['valid_name_ratio']} "
            f"duplicados={source['duplicate_names']} "
            f"ratio_duplicados={source['duplicate_ratio']} "
            f"setor_unknown={source['unknown_sector']} "
            f"ratio_unknown={source['unknown_sector_ratio']} "
            f"confianca_media={source['average_confidence']}"
        )
        print(f"  setores: {source['sectors']}")
        if source["examples"]:
            print("  exemplos:")
            for example in source["examples"]:
                print(
                    "   - "
                    f"{example['startup_name']} "
                    f"({example['sector']}, {example['confidence']}): "
                    f"{example['title']}"
                )


def configured_source_urls(cli_sources: str | None) -> list[str]:
    if cli_sources:
        return parse_discovery_source_urls(cli_sources)
    settings = get_settings()
    return parse_discovery_source_urls(
        settings.startup_discovery_source_urls,
        settings.startup_discovery_source_url,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Valida empiricamente as fontes publicas de descoberta de startups."
    )
    parser.add_argument(
        "--sources",
        help="Lista de URLs separadas por virgula. Por padrao usa a configuracao do app.",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=10,
        help="Maximo de descobertas por fonte.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Imprime o relatorio em JSON.",
    )
    parser.add_argument(
        "--fail-on-empty",
        action="store_true",
        help="Retorna erro se nenhuma descoberta for encontrada.",
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="Retorna erro se alguma fonte ficar em warn ou fail.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source_urls = configured_source_urls(args.sources)
    report = check_sources(source_urls, max_items=max(1, args.max_items))

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text_report(report)

    if args.fail_on_empty and report["total_discoveries"] == 0:
        return 1
    if args.fail_on_warning and (
        report["quality_warn_sources"] > 0 or report["quality_fail_sources"] > 0
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
