#!/usr/bin/env python3
"""Audit NVIDIA corpus freshness, versioning, and deprecation metadata.

The audit is fully offline: it reads the local corpus manifest and does not
fetch, ingest, or mutate any source.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - exercised by local CLI envs without PyYAML
    yaml = None  # type: ignore[assignment]

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_SOURCES_FILE = _PROJECT_ROOT / "data" / "nvidia_corpus" / "sources.yaml"

_REQUIRED_METADATA = [
    "version",
    "content_hash",
    "collected_at",
    "last_checked_at",
    "valid_from",
    "freshness_policy",
    "stale_after_days",
    "is_active",
]


@dataclass
class SourceVersionRecord:
    source_id: str
    title: str
    product: str
    version: str | None
    content_hash: str | None
    previous_content_hash: str | None = None
    collected_at: str | None = None
    last_checked_at: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None
    freshness_policy: str | None = None
    stale_after_days: int | None = None
    is_active: bool | None = None
    deprecated_at: str | None = None
    superseded_by: str | None = None
    deprecation_reason: str | None = None


@dataclass
class CorpusFreshnessAuditReport:
    audit_run_id: str
    generated_at: str
    sources_seen: int = 0
    active_sources: int = 0
    stale_sources: int = 0
    expired_sources: int = 0
    deprecated_sources: int = 0
    superseded_sources: int = 0
    missing_metadata: list[dict[str, Any]] = field(default_factory=list)
    duplicate_active_versions: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    details: dict[str, list[dict[str, Any]]] = field(
        default_factory=lambda: {
            "active_sources": [],
            "stale_sources": [],
            "expired_sources": [],
            "deprecated_sources": [],
            "superseded_sources": [],
        }
    )


def load_sources_manifest(path: Path = _DEFAULT_SOURCES_FILE) -> dict[str, Any]:
    """Load sources.yaml and return source_id -> metadata."""
    if not path.exists():
        return {}
    raw = _load_manifest_text(path.read_text(encoding="utf-8")) or {}
    sources = raw.get("sources", {})
    return sources if isinstance(sources, dict) else {}


def iter_source_versions(sources: dict[str, Any]) -> list[SourceVersionRecord]:
    """Flatten a manifest into source-version records.

    Backward-compatible manifests with only top-level metadata produce one
    record. New manifests with ``versions`` produce one record per version.
    """
    records: list[SourceVersionRecord] = []
    for source_id, info in sources.items():
        if not isinstance(info, dict):
            continue
        versions = info.get("versions")
        if isinstance(versions, list) and versions:
            for version_info in versions:
                if isinstance(version_info, dict):
                    records.append(_build_record(source_id, info, version_info))
        else:
            records.append(_build_record(source_id, info, info))
    return records


def run_audit(
    sources_path: Path = _DEFAULT_SOURCES_FILE,
    *,
    source_ids: list[str] | None = None,
    products: list[str] | None = None,
    now: datetime | None = None,
) -> CorpusFreshnessAuditReport:
    """Run the corpus freshness audit and return a structured report."""
    generated_at_dt = now or datetime.now(UTC)
    generated_at = generated_at_dt.isoformat()
    report = CorpusFreshnessAuditReport(
        audit_run_id=f"audit_{generated_at_dt.strftime('%Y%m%d_%H%M%S')}",
        generated_at=generated_at,
    )

    records = iter_source_versions(load_sources_manifest(sources_path))
    records = _filter_records(records, source_ids=source_ids, products=products)
    report.sources_seen = len(records)

    active_by_source: dict[str, list[SourceVersionRecord]] = {}
    for record in records:
        missing = _missing_metadata(record)
        if missing:
            report.missing_metadata.append(
                {
                    "source_id": record.source_id,
                    "version": record.version,
                    "missing_fields": missing,
                }
            )

        if record.is_active is True:
            report.active_sources += 1
            report.details["active_sources"].append(_record_summary(record))
            active_by_source.setdefault(record.source_id, []).append(record)

        if _is_stale(record, generated_at_dt):
            report.stale_sources += 1
            report.details["stale_sources"].append(_record_summary(record))

        if _is_expired(record, generated_at_dt):
            report.expired_sources += 1
            report.details["expired_sources"].append(_record_summary(record))

        if _is_deprecated(record):
            report.deprecated_sources += 1
            report.details["deprecated_sources"].append(_record_summary(record))

        if record.superseded_by:
            report.superseded_sources += 1
            report.details["superseded_sources"].append(_record_summary(record))

    for source_id, active_records in sorted(active_by_source.items()):
        if len(active_records) > 1:
            report.duplicate_active_versions.append(
                {
                    "source_id": source_id,
                    "active_versions": [r.version for r in active_records],
                }
            )

    report.recommendations = _build_recommendations(report)
    return report


def format_report(report: CorpusFreshnessAuditReport, output_format: str) -> str:
    """Format a report as JSON or Markdown."""
    data = asdict(report)
    if output_format == "json":
        return json.dumps(data, indent=2, ensure_ascii=False)
    if output_format != "markdown":
        raise ValueError(f"Unsupported format: {output_format}")
    lines = [
        "# NVIDIA Corpus Freshness Audit",
        "",
        f"- audit_run_id: `{report.audit_run_id}`",
        f"- generated_at: `{report.generated_at}`",
        f"- sources_seen: {report.sources_seen}",
        f"- active_sources: {report.active_sources}",
        f"- stale_sources: {report.stale_sources}",
        f"- expired_sources: {report.expired_sources}",
        f"- deprecated_sources: {report.deprecated_sources}",
        f"- superseded_sources: {report.superseded_sources}",
        f"- missing_metadata: {len(report.missing_metadata)}",
        f"- duplicate_active_versions: {len(report.duplicate_active_versions)}",
        "",
        "## Recommendations",
    ]
    if report.recommendations:
        lines.extend(f"- {item}" for item in report.recommendations)
    else:
        lines.append("- No action required.")
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit NVIDIA corpus freshness/versioning metadata.",
    )
    parser.add_argument("--report-path", help="Write the audit report to this path.")
    parser.add_argument(
        "--fail-on-stale",
        action="store_true",
        help="Exit with code 1 when stale sources are found.",
    )
    parser.add_argument(
        "--fail-on-expired",
        action="store_true",
        help="Exit with code 1 when expired sources are found.",
    )
    parser.add_argument(
        "--source-id",
        nargs="+",
        default=None,
        help="Audit only these source IDs.",
    )
    parser.add_argument(
        "--product",
        nargs="+",
        default=None,
        help="Audit only sources whose product matches one of these values.",
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        help="Report format.",
    )
    parser.add_argument(
        "--sources-path",
        default=str(_DEFAULT_SOURCES_FILE),
        help=argparse.SUPPRESS,
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    report = run_audit(
        Path(args.sources_path),
        source_ids=args.source_id,
        products=args.product,
    )
    rendered = format_report(report, args.format)

    if args.report_path:
        report_path = Path(args.report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(rendered, encoding="utf-8")
    else:
        print(rendered)

    if args.fail_on_stale and report.stale_sources:
        sys.exit(1)
    if args.fail_on_expired and report.expired_sources:
        sys.exit(1)


def _build_record(
    source_id: str,
    source_info: dict[str, Any],
    version_info: dict[str, Any],
) -> SourceVersionRecord:
    def get(name: str, default: Any = None) -> Any:
        return version_info.get(name, source_info.get(name, default))

    return SourceVersionRecord(
        source_id=source_id,
        title=source_info.get("title", source_id),
        product=source_info.get("product", ""),
        version=get("version"),
        content_hash=get("content_hash"),
        previous_content_hash=get("previous_content_hash"),
        collected_at=get("collected_at"),
        last_checked_at=get("last_checked_at"),
        valid_from=get("valid_from"),
        valid_until=get("valid_until"),
        freshness_policy=get("freshness_policy"),
        stale_after_days=get("stale_after_days"),
        is_active=get("is_active"),
        deprecated_at=get("deprecated_at"),
        superseded_by=get("superseded_by"),
        deprecation_reason=get("deprecation_reason"),
    )


def _load_manifest_text(text: str) -> dict[str, Any]:
    if yaml is not None:
        loaded = yaml.safe_load(text)
        return loaded if isinstance(loaded, dict) else {}
    return _parse_yaml_subset(text)


def _parse_yaml_subset(text: str) -> dict[str, Any]:
    """Parse the small YAML subset used by corpus manifests.

    This fallback keeps the audit CLI usable in minimal local environments where
    PyYAML is not installed. It intentionally supports only dicts, lists of
    dicts, inline scalar lists, strings, ints, booleans, and nulls.
    """
    result: dict[str, Any] = {"sources": {}}
    current_source: dict[str, Any] | None = None
    current_versions: list[dict[str, Any]] | None = None
    current_version: dict[str, Any] | None = None

    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line.strip()

        if indent == 0 and stripped == "sources:":
            continue
        if indent == 2 and stripped.endswith(":"):
            source_id = stripped[:-1]
            current_source = {}
            result["sources"][source_id] = current_source
            current_versions = None
            current_version = None
            continue
        if current_source is None:
            continue
        if indent == 4 and stripped == "versions:":
            current_versions = []
            current_source["versions"] = current_versions
            current_version = None
            continue
        if indent == 4 and ":" in stripped:
            key, value = stripped.split(":", 1)
            current_source[key] = _parse_scalar(value.strip())
            continue
        if indent == 6 and stripped.startswith("- "):
            current_version = {}
            if current_versions is None:
                current_versions = []
                current_source["versions"] = current_versions
            current_versions.append(current_version)
            first = stripped[2:]
            if ":" in first:
                key, value = first.split(":", 1)
                current_version[key] = _parse_scalar(value.strip())
            continue
        if indent == 8 and current_version is not None and ":" in stripped:
            key, value = stripped.split(":", 1)
            current_version[key] = _parse_scalar(value.strip())

    return result


def _parse_scalar(value: str) -> Any:
    if value in ("", "null", "None", "~"):
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part.strip()) for part in inner.split(",")]
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        return value


def _filter_records(
    records: list[SourceVersionRecord],
    *,
    source_ids: list[str] | None,
    products: list[str] | None,
) -> list[SourceVersionRecord]:
    result = records
    if source_ids:
        allowed_ids = set(source_ids)
        result = [r for r in result if r.source_id in allowed_ids]
    if products:
        allowed_products = {p.lower() for p in products}
        result = [r for r in result if r.product.lower() in allowed_products]
    return result


def _missing_metadata(record: SourceVersionRecord) -> list[str]:
    missing: list[str] = []
    values = record.__dict__
    for field_name in _REQUIRED_METADATA:
        if values.get(field_name) is None or values.get(field_name) == "":
            missing.append(field_name)
    if _is_deprecated(record):
        for field_name in ("deprecated_at", "deprecation_reason"):
            if values.get(field_name) is None or values.get(field_name) == "":
                missing.append(field_name)
    return missing


def _is_stale(record: SourceVersionRecord, now: datetime) -> bool:
    if _is_deprecated(record):
        return False
    checked_at = _parse_datetime(record.last_checked_at)
    if checked_at is None or record.stale_after_days is None:
        return False
    return checked_at + timedelta(days=int(record.stale_after_days)) < now


def _is_expired(record: SourceVersionRecord, now: datetime) -> bool:
    if _is_deprecated(record):
        return False
    valid_until = _parse_datetime(record.valid_until)
    if valid_until is None:
        return False
    return valid_until < now


def _is_deprecated(record: SourceVersionRecord) -> bool:
    return record.is_active is False or record.deprecated_at is not None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _record_summary(record: SourceVersionRecord) -> dict[str, Any]:
    return {
        "source_id": record.source_id,
        "version": record.version,
        "product": record.product,
        "content_hash": record.content_hash,
        "is_active": record.is_active,
        "last_checked_at": record.last_checked_at,
        "valid_until": record.valid_until,
        "deprecated_at": record.deprecated_at,
        "superseded_by": record.superseded_by,
        "deprecation_reason": record.deprecation_reason,
    }


def _build_recommendations(report: CorpusFreshnessAuditReport) -> list[str]:
    recommendations: list[str] = []
    if report.missing_metadata:
        recommendations.append("Backfill missing freshness/versioning metadata.")
    if report.duplicate_active_versions:
        recommendations.append("Deactivate superseded versions so each source_id has one active version.")
    if report.stale_sources:
        recommendations.append("Run source sync or manually review stale sources.")
    if report.expired_sources:
        recommendations.append("Deprecate or refresh expired sources before retrieval.")
    if report.deprecated_sources:
        recommendations.append("Ensure deprecated sources are excluded from default retrieval.")
    return recommendations


if __name__ == "__main__":
    main()
