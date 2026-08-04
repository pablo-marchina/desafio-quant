from __future__ import annotations

import hashlib
import re

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.schemas import KnowledgeChunk, KnowledgeMetadata, LoadedKnowledgeDocument


class NVIDIAChunker:
    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 100) -> None:
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap deve ser menor que chunk_size")
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n## ", "\n### ", "\n\n", "\n", ". ", " "],
        )

    def split(self, document: LoadedKnowledgeDocument) -> list[KnowledgeChunk]:
        chunks = []
        for index, content in enumerate(self.splitter.split_text(document.content)):
            section = _section_title(content) or document.titulo
            chunk_id = _stable_chunk_id(document.source.url, index, content)
            metadata = KnowledgeMetadata(
                tecnologia=document.source.tecnologia,
                tipo=document.source.tipo,
                dores_relacionadas=document.source.dores_relacionadas,
                perfil_aplicavel=document.source.perfil_aplicavel,
                titulo_secao=section,
                url_fonte=document.source.url,
            )
            chunks.append(KnowledgeChunk(chunk_id=chunk_id, content=content, metadata=metadata))
        return chunks


def _section_title(content: str) -> str | None:
    match = re.search(r"^#{1,4}\s+(.+)$", content, flags=re.MULTILINE)
    return match.group(1).strip()[:200] if match else None


def _stable_chunk_id(url: str, index: int, content: str) -> str:
    raw = f"{url}|{index}|{content}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
