import json
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException

from app.collector import collect_source
from app.rag.retriever import (
    EMBEDDING_MODEL_NAME,
    build_vector_index,
)
from app.rag.schemas import (
    NvidiaChunk,
    NvidiaIngestResponse,
    NvidiaIngestStatus,
    NvidiaSource,
)


BACKEND_DIR = Path(__file__).resolve().parents[2]

KNOWLEDGE_BASE_DIR = BACKEND_DIR / "knowledge_base"
SOURCES_PATH = KNOWLEDGE_BASE_DIR / "nvidia_sources.json"
RAW_DIR = KNOWLEDGE_BASE_DIR / "raw"
PROCESSED_DIR = KNOWLEDGE_BASE_DIR / "processed"
CHUNKS_PATH = PROCESSED_DIR / "nvidia_chunks.json"

CHUNK_SIZE_WORDS = 380
CHUNK_OVERLAP_WORDS = 70


def ensure_directories() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def load_enabled_sources() -> list[NvidiaSource]:
    if not SOURCES_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail="Arquivo knowledge_base/nvidia_sources.json não encontrado.",
        )

    data = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))

    sources = [
        NvidiaSource.model_validate(item)
        for item in data
    ]

    return [
        source
        for source in sources
        if source.enabled
    ]


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def get_overlap_words(words: list[str]) -> list[str]:
    if len(words) <= CHUNK_OVERLAP_WORDS:
        return words

    return words[-CHUNK_OVERLAP_WORDS:]


def chunk_text(text: str) -> list[str]:
    paragraphs = [
        normalize_whitespace(paragraph)
        for paragraph in re.split(r"\n{2,}", text)
        if normalize_whitespace(paragraph)
    ]

    if not paragraphs:
        return []

    chunks = []
    current_words: list[str] = []

    for paragraph in paragraphs:
        paragraph_words = paragraph.split()

        if (
            current_words
            and len(current_words) + len(paragraph_words)
            > CHUNK_SIZE_WORDS
        ):
            chunks.append(" ".join(current_words))

            current_words = get_overlap_words(current_words)

        current_words.extend(paragraph_words)

        while len(current_words) > CHUNK_SIZE_WORDS:
            chunks.append(
                " ".join(current_words[:CHUNK_SIZE_WORDS])
            )

            current_words = (
                get_overlap_words(
                    current_words[:CHUNK_SIZE_WORDS]
                )
                + current_words[CHUNK_SIZE_WORDS:]
            )

    if current_words:
        chunks.append(" ".join(current_words))

    return [
        chunk
        for chunk in chunks
        if len(chunk.split()) >= 25
    ]


def save_raw_document(
    source: NvidiaSource,
    clean_text: str,
    collected_at: datetime,
) -> None:
    content = (
        f"# {source.title}\n\n"
        f"Technology: {source.technology_name}\n"
        f"Source URL: {source.source_url}\n"
        f"Collected at: {collected_at.isoformat()}\n"
        f"Tags: {', '.join(source.tags)}\n\n"
        f"{clean_text}\n"
    )

    raw_path = RAW_DIR / f"{source.technology_id}.md"

    raw_path.write_text(
        content,
        encoding="utf-8",
    )


async def ingest_nvidia_knowledge_base() -> NvidiaIngestResponse:
    ensure_directories()

    sources = load_enabled_sources()

    if not sources:
        raise HTTPException(
            status_code=422,
            detail=(
                "Nenhuma fonte NVIDIA está habilitada em "
                "knowledge_base/nvidia_sources.json."
            ),
        )

    all_chunks: list[NvidiaChunk] = []
    statuses: list[NvidiaIngestStatus] = []

    for source in sources:
        try:
            collected = await collect_source(
                startup_name=(
                    f"NVIDIA Knowledge Base - "
                    f"{source.technology_name}"
                ),
                url=str(source.source_url),
            )

            collected_at = datetime.now(timezone.utc)

            save_raw_document(
                source=source,
                clean_text=collected.clean_text,
                collected_at=collected_at,
            )

            source_chunks = chunk_text(collected.clean_text)

            for index, text in enumerate(source_chunks, start=1):
                all_chunks.append(
                    NvidiaChunk(
                        chunk_id=(
                            f"{source.technology_id}_{index:03d}"
                        ),
                        technology_id=source.technology_id,
                        technology_name=source.technology_name,
                        title=source.title,
                        text=text,
                        source_url=str(source.source_url),
                        source_type=source.source_type,
                        tags=source.tags,
                        chunk_index=index,
                        word_count=len(text.split()),
                        collected_at=collected_at,
                    )
                )

            statuses.append(
                NvidiaIngestStatus(
                    technology_id=source.technology_id,
                    technology_name=source.technology_name,
                    source_url=str(source.source_url),
                    status="COLLECTED",
                    chunks_created=len(source_chunks),
                    text_characters=collected.text_characters,
                )
            )

        except HTTPException as error:
            statuses.append(
                NvidiaIngestStatus(
                    technology_id=source.technology_id,
                    technology_name=source.technology_name,
                    source_url=str(source.source_url),
                    status="FAILED",
                    error=str(error.detail),
                )
            )

    if not all_chunks:
        raise HTTPException(
            status_code=422,
            detail=(
                "Nenhuma fonte oficial NVIDIA pôde ser coletada. "
                "Verifique os status de coleta."
            ),
        )

    CHUNKS_PATH.write_text(
        json.dumps(
            [
                chunk.model_dump(mode="json")
                for chunk in all_chunks
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    build_vector_index(all_chunks)

    successful_count = sum(
        1
        for status in statuses
        if status.status == "COLLECTED"
    )

    return NvidiaIngestResponse(
        collected_at=datetime.now(timezone.utc),
        sources_processed=len(statuses),
        sources_successful=successful_count,
        sources_failed=len(statuses) - successful_count,
        chunks_created=len(all_chunks),
        embedding_model=EMBEDDING_MODEL_NAME,
        statuses=statuses,
    )