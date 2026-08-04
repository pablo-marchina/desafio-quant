from dataclasses import dataclass

from app.rag.catalog import NVIDIA_TECHNOLOGY_CATALOG
from app.rag.chunking import chunk_text


@dataclass(frozen=True)
class PreparedKnowledgeDocument:
    title: str
    url: str
    product_area: str
    text: str
    chunks: tuple[str, ...]


def prepare_seed_knowledge_documents() -> list[PreparedKnowledgeDocument]:
    documents: list[PreparedKnowledgeDocument] = []

    for catalog_item in NVIDIA_TECHNOLOGY_CATALOG:
        text = (
            f"{catalog_item.name}. {catalog_item.description} "
            f"Relevant keywords: {', '.join(catalog_item.keywords)}."
        )
        documents.append(
            PreparedKnowledgeDocument(
                title=catalog_item.name,
                url=catalog_item.source_url,
                product_area=catalog_item.category,
                text=text,
                chunks=tuple(chunk_text(text)),
            )
        )

    return documents
