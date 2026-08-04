from app.rag.ingestion import prepare_seed_knowledge_documents


def main() -> None:
    prepared_documents = prepare_seed_knowledge_documents()

    for document in prepared_documents:
        print(f"{document.title} | {document.url} | chunks={len(document.chunks)}")


if __name__ == "__main__":
    main()
