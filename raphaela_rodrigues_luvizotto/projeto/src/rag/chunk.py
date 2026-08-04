import json
import logging
from pathlib import Path
from typing import Dict, List

from .config import CHUNK_OVERLAP, CHUNK_SIZE, NVIDIA_KB_CHUNKS_DIR, NVIDIA_KB_PROCESSED_DIR
from .ingest import load_processed_docs

logger = logging.getLogger(__name__)


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Chunking simples baseado em palavras.
    """
    words = text.split()
    if not words:
        return []

    if overlap >= chunk_size:
        raise ValueError("overlap deve ser menor que chunk_size")

    chunks: List[str] = []
    step = chunk_size - overlap
    start = 0

    while start < len(words):
        end = start + chunk_size
        chunk_words = words[start:end]
        if not chunk_words:
            break
        chunks.append(" ".join(chunk_words).strip())
        start += step

    return chunks


def build_chunks_for_document(
    doc: Dict,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> List[Dict]:
    """
    Gera chunks de um documento processado preservando os metadados relevantes.
    """
    document_id = doc.get("id")
    content = doc.get("conteudo", "")
    text_chunks = chunk_text(content, chunk_size=chunk_size, overlap=overlap)

    chunk_docs: List[Dict] = []
    for index, text_chunk in enumerate(text_chunks, start=1):
        chunk_docs.append(
            {
                "id": f"{document_id}_chunk_{index:03d}",
                "document_id": document_id,
                "titulo": doc.get("titulo"),
                "nome_produto": doc.get("nome_produto"),
                "categoria": doc.get("categoria"),
                "texto_chunk": text_chunk,
                "chunk_index": index,
                "url_pesquisa": doc.get("url_pesquisa"),
                "tags": doc.get("tags", []),
                "caso_uso": doc.get("caso_uso", []),
                "fonte_tipo": doc.get("fonte_tipo"),
                "coletado_em": doc.get("coletado_em"),
            }
        )

    return chunk_docs


def save_chunk_documents(chunks: List[Dict], output_dir: Path = NVIDIA_KB_CHUNKS_DIR) -> Path:
    """
    Salva a lista agregada de chunks em disco.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "chunks.json"
    output_path.write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def generate_and_save_chunks(
    source_dir: Path = NVIDIA_KB_PROCESSED_DIR,
    output_dir: Path = NVIDIA_KB_CHUNKS_DIR,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> List[Dict]:
    """
    Carrega documentos processados, gera chunks e salva um arquivo consolidado.
    """
    all_chunks: List[Dict] = []

    for doc in load_processed_docs(source_dir):
        if not doc.get("conteudo"):
            logger.warning("Documento sem conteudo ignorado: %s", doc.get("id"))
            continue

        doc_chunks = build_chunks_for_document(
            doc,
            chunk_size=chunk_size,
            overlap=overlap,
        )
        all_chunks.extend(doc_chunks)
        logger.info("Documento %s gerou %d chunks", doc.get("id"), len(doc_chunks))

    save_chunk_documents(all_chunks, output_dir=output_dir)
    logger.info("Total de chunks salvos: %d", len(all_chunks))
    return all_chunks


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    chunks = generate_and_save_chunks()
    print(f"{len(chunks)} chunks salvos em {NVIDIA_KB_CHUNKS_DIR}")
