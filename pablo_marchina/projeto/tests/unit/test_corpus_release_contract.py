from __future__ import annotations

from pathlib import Path

import yaml


CORPUS_ROOT = Path("data/nvidia_corpus")
SOURCES_PATH = CORPUS_ROOT / "sources.yaml"
KEYWORDS_PATH = CORPUS_ROOT / "retrieval_keywords.yaml"


def _active_sources() -> dict[str, dict]:
    payload = yaml.safe_load(SOURCES_PATH.read_text(encoding="utf-8")) or {}
    sources = payload.get("sources", {})
    return {
        source_id: metadata
        for source_id, metadata in sources.items()
        if isinstance(metadata, dict) and metadata.get("is_active", True) is True
    }


def _keyword_registry() -> dict[str, list[str]]:
    payload = yaml.safe_load(KEYWORDS_PATH.read_text(encoding="utf-8")) or {}
    return payload.get("keywords", {})


def test_every_active_source_has_a_non_placeholder_document() -> None:
    failures: list[str] = []
    for source_id in sorted(_active_sources()):
        path = CORPUS_ROOT / f"{source_id}.md"
        if not path.is_file():
            failures.append(f"{source_id}: missing {path}")
            continue
        content = path.read_text(encoding="utf-8").strip()
        if "placeholder" in content.casefold():
            failures.append(f"{source_id}: active corpus document is still a placeholder")
        if len(content) < 180:
            failures.append(f"{source_id}: active corpus document is too small ({len(content)} chars)")
    assert not failures, "\n".join(failures)


def test_every_active_source_has_governed_retrieval_keywords() -> None:
    keywords = _keyword_registry()
    failures: list[str] = []
    for source_id in sorted(_active_sources()):
        aliases = keywords.get(source_id)
        if not isinstance(aliases, list) or not [alias for alias in aliases if str(alias).strip()]:
            failures.append(f"{source_id}: missing governed retrieval keywords")
    assert not failures, "\n".join(failures)


def test_keyword_registry_does_not_reference_inactive_or_unknown_sources() -> None:
    active = set(_active_sources())
    registered = set(_keyword_registry())
    assert registered == active, (
        f"keyword registry drift: missing={sorted(active - registered)}, "
        f"unknown_or_inactive={sorted(registered - active)}"
    )
