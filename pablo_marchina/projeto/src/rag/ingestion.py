"""NVIDIA corpus ingestion, content cleaning, and deterministic chunking."""

from __future__ import annotations

import re
from math import ceil
from pathlib import Path

import trafilatura
import yaml
from bs4 import BeautifulSoup

from src.rag.schemas import RagChunk, RagDocument, RagSource

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CORPUS_DIR = _PROJECT_ROOT / "data" / "nvidia_corpus"
_SOURCES_FILE = _CORPUS_DIR / "sources.yaml"
_MAX_UNSTRUCTURED_CHUNKS = 5
_MIN_TARGET_CHARS = 800
_HTML_MARKER = re.compile(r"<(?:!doctype|html|head|body|main|article)\b", re.IGNORECASE)


def load_sources() -> dict[str, RagSource]:
    """Load source metadata from sources.yaml."""
    if not _SOURCES_FILE.exists():
        return {}
    raw = _SOURCES_FILE.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    sources_raw = data.get("sources", {})
    sources: dict[str, RagSource] = {}
    for sid, info in sources_raw.items():
        active_info = _active_version_info(info)
        sources[sid] = RagSource(
            source_id=sid,
            title=info.get("title", sid),
            url=info.get("url"),
            product=info.get("product", ""),
            gap_types=info.get("gap_types", []),
            version=active_info.get("version", info.get("version", "1.0")),
            document_type=info.get("document_type", "nvidia_corpus"),
            content_hash=active_info.get("content_hash", info.get("content_hash")),
            previous_content_hash=active_info.get("previous_content_hash", info.get("previous_content_hash")),
            collected_at=active_info.get("collected_at", info.get("collected_at")),
            last_checked_at=active_info.get("last_checked_at", info.get("last_checked_at")),
            valid_from=active_info.get("valid_from", info.get("valid_from")),
            valid_until=active_info.get("valid_until", info.get("valid_until")),
            freshness_policy=active_info.get("freshness_policy", info.get("freshness_policy")),
            stale_after_days=active_info.get("stale_after_days", info.get("stale_after_days")),
            is_active=active_info.get("is_active", info.get("is_active", True)),
            deprecated_at=active_info.get("deprecated_at", info.get("deprecated_at")),
            superseded_by=active_info.get("superseded_by", info.get("superseded_by")),
            deprecation_reason=active_info.get("deprecation_reason", info.get("deprecation_reason")),
        )
    return sources


def _active_version_info(info: dict) -> dict:
    versions = info.get("versions")
    if not isinstance(versions, list):
        return info
    active_versions = [v for v in versions if isinstance(v, dict) and v.get("is_active") is True]
    if active_versions:
        return active_versions[-1]
    return versions[-1] if versions and isinstance(versions[-1], dict) else info


def load_markdown_document(path: Path) -> RagDocument | None:
    """Load a corpus file and remove HTML/navigation noise before indexing.

    Source synchronization can persist an HTML response in a ``.md`` file. Raw
    HTML used to flow directly into chunking, which increased memory, indexing
    time, and false lexical matches on CSS/navigation text. The ingestion
    boundary now normalizes those files into clean, human-readable content.
    """
    if not path.exists() or path.suffix not in (".md", ".markdown"):
        return None

    raw_text = path.read_text(encoding="utf-8")
    source_id = path.stem
    html_title = _extract_html_title(raw_text) if _looks_like_html(raw_text) else None
    cleaned_text = _clean_document_text(raw_text)
    title = _extract_title(cleaned_text) or html_title or source_id
    return RagDocument(source_id=source_id, title=title, raw_text=cleaned_text)


def _looks_like_html(text: str) -> bool:
    return bool(_HTML_MARKER.search(text[:5000]))


def _extract_html_title(text: str) -> str | None:
    soup = BeautifulSoup(text, "html.parser")
    for selector, attribute in (
        ("meta[property='og:title']", "content"),
        ("meta[name='title']", "content"),
    ):
        element = soup.select_one(selector)
        if element and element.get(attribute):
            return str(element.get(attribute)).strip()
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    heading = soup.find("h1")
    return heading.get_text(" ", strip=True) if heading else None


def _clean_document_text(text: str) -> str:
    if not _looks_like_html(text):
        return text.strip()

    extracted = trafilatura.extract(
        text,
        output_format="markdown",
        include_comments=False,
        include_tables=True,
        include_links=False,
        include_images=False,
        favor_precision=True,
        deduplicate=True,
    )
    if extracted and len(extracted.strip()) >= 120:
        return extracted.strip()

    soup = BeautifulSoup(text, "html.parser")
    for element in soup(["script", "style", "noscript", "template", "svg", "nav", "footer", "header"]):
        element.decompose()
    fallback = soup.get_text("\n", strip=True)
    return re.sub(r"\n{3,}", "\n\n", fallback).strip()


def _extract_title(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            return stripped[2:].strip()
    return None


def _validate_active_document(doc: RagDocument) -> None:
    content = doc.raw_text.strip()
    if not content:
        raise RuntimeError(f"Active NVIDIA corpus source is empty: {doc.source_id}")
    if "placeholder" in content.casefold():
        raise RuntimeError(f"Active NVIDIA corpus source is still a placeholder: {doc.source_id}")


def chunk_document(doc: RagDocument, sources: dict[str, RagSource]) -> list[RagChunk]:
    """Split a document by meaningful sections or bounded text groups."""
    source_info = sources.get(doc.source_id)
    section_chunks = _markdown_sections(doc.raw_text)

    if not section_chunks:
        section_chunks = _chunk_unstructured_text(doc.raw_text)

    chunks: list[RagChunk] = []
    for index, (heading, content) in enumerate(section_chunks):
        if not content.strip():
            continue
        chunks.append(
            _make_chunk(
                doc=doc,
                source_info=source_info,
                index=index,
                heading=heading or doc.title,
                content=content.strip(),
            )
        )
    return chunks


def _markdown_sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current_section: list[str] = []
    current_heading = ""

    for line in text.splitlines():
        if line.startswith("## "):
            if current_section and current_heading:
                content = "\n".join(current_section).strip()
                if content:
                    sections.append((current_heading, content))
            current_heading = line[3:].strip()
            current_section = [line]
        else:
            current_section.append(line)

    if current_section and current_heading:
        content = "\n".join(current_section).strip()
        if content:
            sections.append((current_heading, content))
    return sections


def _chunk_unstructured_text(text: str) -> list[tuple[str, str]]:
    """Preserve full text while bounding unstructured documents to five chunks."""
    normalized = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not normalized:
        return []

    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", normalized) if paragraph.strip()]
    if not paragraphs:
        paragraphs = [normalized]

    total_chars = sum(len(paragraph) for paragraph in paragraphs)
    target_size = max(_MIN_TARGET_CHARS, ceil(total_chars / _MAX_UNSTRUCTURED_CHUNKS))
    chunks: list[tuple[str, str]] = []
    current: list[str] = []
    current_chars = 0

    for paragraph in paragraphs:
        remaining_slots = _MAX_UNSTRUCTURED_CHUNKS - len(chunks)
        should_flush = (
            current
            and current_chars + len(paragraph) > target_size
            and remaining_slots > 1
        )
        if should_flush:
            chunks.append((f"Part {len(chunks) + 1}", "\n\n".join(current)))
            current = []
            current_chars = 0
        current.append(paragraph)
        current_chars += len(paragraph)

    if current:
        chunks.append((f"Part {len(chunks) + 1}", "\n\n".join(current)))
    return chunks


def _make_chunk(
    doc: RagDocument,
    source_info: RagSource | None,
    index: int,
    heading: str,
    content: str,
) -> RagChunk:
    heading_prefix = heading.strip()
    if heading_prefix and not content.lstrip().startswith(("#", heading_prefix)):
        content = f"## {heading_prefix}\n\n{content}"

    return RagChunk(
        chunk_id=f"{doc.source_id}_{index:03d}",
        source_id=doc.source_id,
        title=doc.title,
        content=content,
        product=source_info.product if source_info else doc.title,
        gap_types=source_info.gap_types if source_info else [],
        url=source_info.url if source_info else None,
        version=source_info.version if source_info else "1.0",
        document_type=source_info.document_type if source_info else "nvidia_corpus",
        content_hash=source_info.content_hash if source_info else None,
        previous_content_hash=source_info.previous_content_hash if source_info else None,
        collected_at=source_info.collected_at if source_info else None,
        last_checked_at=source_info.last_checked_at if source_info else None,
        valid_from=source_info.valid_from if source_info else None,
        valid_until=source_info.valid_until if source_info else None,
        freshness_policy=source_info.freshness_policy if source_info else None,
        stale_after_days=source_info.stale_after_days if source_info else None,
        is_active=source_info.is_active if source_info else True,
        deprecated_at=source_info.deprecated_at if source_info else None,
        superseded_by=source_info.superseded_by if source_info else None,
        deprecation_reason=source_info.deprecation_reason if source_info else None,
        nvidia_technology=source_info.product if source_info else "",
        corpus_version=source_info.version if source_info else "1.0",
        chunk_index=index,
        char_count=len(content),
    )


def load_and_chunk_corpus() -> list[RagChunk]:
    """Load all active, governed markdown files from the corpus directory."""
    sources = load_sources()
    all_chunks: list[RagChunk] = []
    if not _CORPUS_DIR.exists():
        return all_chunks
    active_source_ids = {sid for sid, src in sources.items() if getattr(src, "is_active", True)}
    for md_path in sorted(_CORPUS_DIR.glob("*.md")):
        if md_path.name == "README.md":
            continue
        source_id = md_path.stem
        # Production corpus is allowlist-driven. Test fixtures, stale files or
        # ad-hoc markdown files cannot enter retrieval unless they are active in
        # sources.yaml.
        if source_id not in active_source_ids:
            continue
        doc = load_markdown_document(md_path)
        if doc is None:
            continue
        _validate_active_document(doc)
        all_chunks.extend(chunk_document(doc, sources))
    return all_chunks
