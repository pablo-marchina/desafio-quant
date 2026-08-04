from __future__ import annotations

import csv
import unicodedata
from pathlib import Path
from typing import Iterable

from app.startup_catalog import STARTUP_CANDIDATES


REPO_ROOT = Path(__file__).resolve().parents[3]
STARTUP_SOURCE_FIELDS = [
    "startup_name",
    "country_code",
    "sector",
    "stage",
    "source",
    "website_url",
    "github_url",
    "source_url",
    "description",
    "signals",
]


def normalize_text(value: object) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "").lower())
    return "".join(
        character for character in normalized if not unicodedata.combining(character)
    )


def resolve_source_path(source_path: str) -> Path:
    path = Path(source_path)
    return path if path.is_absolute() else REPO_ROOT / path


def split_signals(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    text = str(value or "")
    delimiter = ";" if ";" in text else ","
    return [item.strip() for item in text.split(delimiter) if item.strip()]


def normalize_candidate(row: dict[str, object]) -> dict[str, object]:
    return {
        "startup_name": str(row.get("startup_name") or row.get("name") or "").strip(),
        "country_code": str(row.get("country_code") or "BR").strip().upper(),
        "sector": str(row.get("sector") or "unknown").strip(),
        "stage": str(row.get("stage") or "").strip() or None,
        "source": str(row.get("source") or "external_source").strip(),
        "website_url": str(row.get("website_url") or "").strip() or None,
        "github_url": str(row.get("github_url") or "").strip() or None,
        "source_url": str(row.get("source_url") or row.get("website_url") or "").strip()
        or None,
        "description": str(row.get("description") or "").strip(),
        "signals": split_signals(row.get("signals")),
    }


def load_startup_candidates(source_path: str) -> list[dict[str, object]]:
    path = resolve_source_path(source_path)
    if not path.exists():
        return [normalize_candidate(candidate) for candidate in STARTUP_CANDIDATES]

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = [
            normalize_candidate(row)
            for row in csv.DictReader(file)
            if str(row.get("startup_name") or row.get("name") or "").strip()
        ]

    return rows or [normalize_candidate(candidate) for candidate in STARTUP_CANDIDATES]


def serialize_candidate(candidate: dict[str, object]) -> dict[str, str]:
    normalized = normalize_candidate(candidate)
    return {
        "startup_name": str(normalized["startup_name"]),
        "country_code": str(normalized["country_code"]),
        "sector": str(normalized["sector"]),
        "stage": str(normalized["stage"] or ""),
        "source": str(normalized["source"]),
        "website_url": str(normalized["website_url"] or ""),
        "github_url": str(normalized["github_url"] or ""),
        "source_url": str(normalized["source_url"] or ""),
        "description": str(normalized["description"]),
        "signals": ";".join(str(signal) for signal in normalized["signals"]),
    }


def write_startup_candidates(source_path: str, candidates: list[dict[str, object]]) -> None:
    path = resolve_source_path(source_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=STARTUP_SOURCE_FIELDS)
        writer.writeheader()
        for candidate in candidates:
            writer.writerow(serialize_candidate(candidate))


def startup_source_status(source_path: str) -> dict[str, object]:
    path = resolve_source_path(source_path)
    exists = path.exists()
    return {
        "path": str(path),
        "exists": exists,
        "source": "csv" if exists else "fallback_catalog",
    }


def candidate_search_text(candidate: dict[str, object]) -> str:
    parts = [
        candidate.get("startup_name"),
        candidate.get("sector"),
        candidate.get("stage"),
        candidate.get("description"),
        " ".join(str(signal) for signal in candidate.get("signals", [])),
        candidate.get("website_url"),
        candidate.get("source_url"),
    ]
    return " ".join(str(part) for part in parts if part)


def score_candidate_match(candidate: dict[str, object], query: str) -> int:
    normalized_query = normalize_text(query).strip()
    if not normalized_query:
        return 0

    name = normalize_text(candidate.get("startup_name"))
    searchable = normalize_text(candidate_search_text(candidate))
    compact_query = "".join(normalized_query.split())
    compact_name = "".join(name.split())
    query_terms = {term for term in normalized_query.split() if len(term) > 1}
    searchable_terms = {term for term in searchable.split() if len(term) > 1}

    score = 0
    if name == normalized_query or compact_name == compact_query:
        score += 120
    elif name.startswith(normalized_query) or compact_name.startswith(compact_query):
        score += 85
    elif (
        normalized_query in name
        or compact_query in compact_name
        or compact_name in compact_query
    ):
        score += 70
    elif normalized_query in searchable:
        score += 45

    score += len(query_terms & searchable_terms) * 8
    if str(candidate.get("country_code", "")).upper() == "BR":
        score += 4
    return score


def search_startup_candidates(
    candidates: Iterable[dict[str, object]],
    query: str,
    limit: int = 8,
) -> list[dict[str, object]]:
    ranked = []
    for candidate in candidates:
        score = score_candidate_match(candidate, query)
        if score <= 0:
            continue
        enriched = dict(candidate)
        enriched["match_score"] = score
        ranked.append(enriched)

    ranked.sort(key=lambda item: int(item.get("match_score") or 0), reverse=True)
    return ranked[:limit]


def resolve_startup_by_name(
    candidates: Iterable[dict[str, object]],
    startup_name: str,
) -> dict[str, object] | None:
    matches = search_startup_candidates(candidates, startup_name, limit=1)
    if not matches:
        return None

    match = matches[0]
    return match if int(match.get("match_score") or 0) >= 50 else None
