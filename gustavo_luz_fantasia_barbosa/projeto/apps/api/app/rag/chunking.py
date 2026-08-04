from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    text: str
    chunk_index: int


def chunk_text(text: str, max_chars: int = 900, overlap: int = 120) -> list[TextChunk]:
    clean_text = " ".join(text.split())
    if not clean_text:
        return []

    chunks: list[TextChunk] = []
    start = 0

    while start < len(clean_text):
        end = min(start + max_chars, len(clean_text))
        if end < len(clean_text):
            sentence_boundary = clean_text.rfind(". ", start, end)
            if sentence_boundary > start + max_chars // 2:
                end = sentence_boundary + 1

        chunks.append(TextChunk(text=clean_text[start:end].strip(), chunk_index=len(chunks)))

        if end >= len(clean_text):
            break
        start = max(0, end - overlap)

    return chunks

