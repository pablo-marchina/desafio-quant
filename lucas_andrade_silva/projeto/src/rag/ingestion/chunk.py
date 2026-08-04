import hashlib
import json
from collections import Counter

from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag.settings import CHUNKS_PATH, DOCUMENTS_PATH

MIN_CONTENT_CHARS = 100


def chunk_id(url: str, index: int) -> str:
    url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return f"{url_hash}__chunk_{index}"


def build_chunks(documents: list[dict]) -> list[dict]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=512,
        chunk_overlap=50,
        separators=["\n\n", "\n", ".", " "],
    )
    chunks = []

    for document in documents:
        if document["chars"] <= MIN_CONTENT_CHARS:
            continue

        for index, text in enumerate(splitter.split_text(document["content"])):
            chunks.append(
                {
                    "chunk_id": chunk_id(document["url"], index),
                    "text": text,
                    "source_url": document["url"],
                    "services": document["services"],
                    "categories": document["categories"],
                    "scraped_at": document["scraped_at"],
                    "scraper_source": document["scraper_source"],
                }
            )

    return chunks


def main() -> None:
    with DOCUMENTS_PATH.open("r", encoding="utf-8") as file:
        documents = json.load(file)

    chunks = build_chunks(documents)
    CHUNKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CHUNKS_PATH.open("w", encoding="utf-8") as file:
        json.dump(chunks, file, ensure_ascii=False, indent=2)

    print(f"Documentos processados: {len(documents)}")
    print(f"Total de chunks gerados: {len(chunks)}")
    print("Por categoria:", dict(Counter(c for chunk in chunks for c in chunk["categories"])))
    print("Por servico:", dict(Counter(s for chunk in chunks for s in chunk["services"])))


if __name__ == "__main__":
    main()
