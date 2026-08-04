import re


def chunk_text(text: str, max_words: int = 180, overlap_words: int = 30) -> list[str]:
    normalized_text = re.sub(r"\s+", " ", text).strip()
    if not normalized_text:
        return []

    words = normalized_text.split(" ")
    if len(words) <= max_words:
        return [normalized_text]

    chunks: list[str] = []
    start_index = 0

    while start_index < len(words):
        end_index = min(start_index + max_words, len(words))
        chunks.append(" ".join(words[start_index:end_index]))

        if end_index == len(words):
            break

        start_index = max(end_index - overlap_words, start_index + 1)

    return chunks
