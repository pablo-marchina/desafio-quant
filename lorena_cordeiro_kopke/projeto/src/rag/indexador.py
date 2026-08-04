"""
Popula o banco vetorial Qdrant a partir de arquivos JSON locais.

Cada arquivo JSON representa um documento (tecnologia, caso de uso, etc.)
e deve seguir o schema definido em data/nvidia_knowledge/_schema.json.

Uso:
    # Indexa todos os JSONs da pasta padrão
    python -m src.rag.indexador

    # Indexa um arquivo específico
    python -m src.rag.indexador --arquivo data/nvidia_knowledge/nim.json

    # Indexa uma pasta alternativa
    python -m src.rag.indexador --pasta data/outra_pasta
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import uuid
from datetime import date
from pathlib import Path

import tiktoken
from qdrant_client.models import PointStruct

from rag.client import get_client
from rag.embedding import gerar_embedding
from rag.setup_qdrant import COLLECTION_NAME

_ENCODING = tiktoken.get_encoding("cl100k_base")
_CHUNK_SIZE = 400
_CHUNK_OVERLAP = 50

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s — %(message)s",
)
logger = logging.getLogger(__name__)

# src/rag/ → src/ → project root → data/nvidia_knowledge/
PASTA_PADRAO = Path(__file__).resolve().parent.parent.parent / "data" / "nvidia_knowledge"

# ---------------------------------------------------------------------------
# Campos obrigatórios e valores válidos
# ---------------------------------------------------------------------------

_CAMPOS_OBRIGATORIOS = {
    "url", "fonte", "titulo", "categoria",
    "familia", "tecnologia", "setores", "ia_tipos", "texto",
}

_CATEGORIAS_VALIDAS = {"produto", "conceito", "caso_de_uso", "inception", "stack"}
_FAMILIAS_VALIDAS   = {"inferencia", "treinamento", "dados", "deployment", "plataforma"}
_SETORES_VALIDOS    = {"saude", "financas", "agro", "varejo", "industria",
                       "educacao", "energia", "logistica", "geral"}
_IA_TIPOS_VALIDOS   = {"visão computacional", "NLP", "LLM", "recomendacao",
                       "series temporais", "deteccao de anomalias", "classificacao",
                       "geracao de conteudo", "busca semantica"}


# ---------------------------------------------------------------------------
# Primitiva de indexação (usada por indexar_json)
# ---------------------------------------------------------------------------


def indexar_documento(texto: str, metadata: dict) -> str:
    """Gera embedding e insere um chunk na collection. Retorna o ID gerado."""
    client = get_client()
    embedding = gerar_embedding(texto)
    doc_id = str(uuid.uuid4())

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            PointStruct(
                id=doc_id,
                vector=embedding,
                payload={"texto": texto, **metadata},
            )
        ],
    )
    return doc_id


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------


def chunkar_texto(texto: str) -> list[str]:
    """Divide o texto em chunks de ~400 tokens com overlap de 50, nunca cortando no meio de uma frase."""
    sentences = re.split(r"(?<=[.!?…])\s+", texto.strip())
    sentences = [s for s in sentences if s.strip()]

    chunks: list[str] = []
    current_sentences: list[str] = []
    current_token_count = 0

    for sentence in sentences:
        sentence_tokens = len(_ENCODING.encode(sentence))

        if current_sentences and current_token_count + sentence_tokens > _CHUNK_SIZE:
            chunks.append(" ".join(current_sentences))

            overlap_sentences: list[str] = []
            overlap_tokens = 0
            for s in reversed(current_sentences):
                t = len(_ENCODING.encode(s))
                if overlap_tokens + t > _CHUNK_OVERLAP:
                    break
                overlap_sentences.insert(0, s)
                overlap_tokens += t

            current_sentences = overlap_sentences
            current_token_count = overlap_tokens

        current_sentences.append(sentence)
        current_token_count += sentence_tokens

    if current_sentences:
        chunks.append(" ".join(current_sentences))

    return [c for c in chunks if c.strip()]


# ---------------------------------------------------------------------------
# Validação
# ---------------------------------------------------------------------------


def _validar(doc: dict, caminho: Path) -> list[str]:
    erros: list[str] = []

    faltando = _CAMPOS_OBRIGATORIOS - doc.keys()
    if faltando:
        erros.append(f"Campos faltando: {sorted(faltando)}")

    if "categoria" in doc and doc["categoria"] not in _CATEGORIAS_VALIDAS:
        erros.append(f"categoria inválida: '{doc['categoria']}'. Válidas: {_CATEGORIAS_VALIDAS}")

    if "familia" in doc and doc["familia"] not in _FAMILIAS_VALIDAS:
        erros.append(f"familia inválida: '{doc['familia']}'. Válidas: {_FAMILIAS_VALIDAS}")

    if "setores" in doc:
        invalidos = set(doc["setores"]) - _SETORES_VALIDOS
        if invalidos:
            erros.append(f"setores inválidos: {invalidos}. Válidos: {_SETORES_VALIDOS}")

    if "ia_tipos" in doc:
        invalidos = set(doc["ia_tipos"]) - _IA_TIPOS_VALIDOS
        if invalidos:
            erros.append(f"ia_tipos inválidos: {invalidos}. Válidos: {_IA_TIPOS_VALIDOS}")

    if "texto" in doc and len(doc["texto"].strip()) < 50:
        erros.append("'texto' muito curto (mínimo 50 caracteres)")

    return erros


# ---------------------------------------------------------------------------
# Indexação de um documento JSON (chunkifica + indexa cada chunk)
# ---------------------------------------------------------------------------


def indexar_json(doc: dict) -> int:
    """Chunkifica o texto do doc e indexa cada chunk. Retorna o número de chunks."""
    texto = doc["texto"]
    metadata_base = {k: v for k, v in doc.items() if k != "texto"}
    metadata_base.setdefault("data_coleta", date.today().isoformat())

    # Prefixo adicionado ao texto embeddado para que cada chunk carregue o contexto
    # da tecnologia e do documento — sem isso, chunks intermediários perdem referência
    # ao que estão descrevendo, degradando a qualidade da busca semântica.
    # O metadata no Qdrant não é alterado; só o texto enviado ao modelo de embedding muda.
    prefixo = f"Tecnologia: {doc.get('tecnologia', '')}. {doc.get('titulo', '')}.\n\n"

    chunks = chunkar_texto(texto)
    if not chunks:
        logger.warning("Nenhum chunk gerado para '%s'", doc.get("titulo", "?"))
        return 0

    doc_id = str(uuid.uuid4())
    chunk_total = len(chunks)

    for i, chunk in enumerate(chunks):
        metadata = {
            **metadata_base,
            "doc_id":      doc_id,
            "chunk_index": i,
            "chunk_total": chunk_total,
        }
        indexar_documento(prefixo + chunk, metadata)

    return chunk_total


# ---------------------------------------------------------------------------
# Processamento de arquivo / pasta
# ---------------------------------------------------------------------------


def processar_arquivo(caminho: Path) -> int:
    if caminho.name.startswith("_"):
        logger.info("Pulando arquivo de schema/template: %s", caminho.name)
        return 0

    logger.info("Lendo %s", caminho)
    try:
        with caminho.open(encoding="utf-8") as f:
            conteudo = json.load(f)
    except json.JSONDecodeError as exc:
        logger.error("JSON inválido em %s: %s", caminho, exc)
        return 0

    # Aceita um único doc (dict) ou uma lista de docs
    documentos: list[dict] = conteudo if isinstance(conteudo, list) else [conteudo]

    total = 0
    for idx, doc in enumerate(documentos, start=1):
        label = f"{caminho.name}[{idx}]" if len(documentos) > 1 else caminho.name
        erros = _validar(doc, caminho)
        if erros:
            logger.error("Documento '%s' inválido:\n  %s", label, "\n  ".join(erros))
            continue

        try:
            n = indexar_json(doc)
            logger.info("  ✓ '%s' → %d chunks indexados", doc.get("titulo", label), n)
            total += n
        except Exception as exc:
            logger.error("  ✗ Erro ao indexar '%s': %s", label, exc, exc_info=True)

    return total


def processar_pasta(pasta: Path) -> int:
    arquivos = sorted(pasta.glob("*.json"))
    if not arquivos:
        logger.warning("Nenhum arquivo .json encontrado em %s", pasta)
        return 0

    total = 0
    for arquivo in arquivos:
        total += processar_arquivo(arquivo)

    return total


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Popula o Qdrant via arquivos JSON.")
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--arquivo", type=Path, help="Caminho para um único arquivo JSON")
    grupo.add_argument("--pasta",   type=Path, help="Pasta com arquivos JSON (padrão: data/nvidia_knowledge/)")
    args = parser.parse_args()

    if args.arquivo:
        if not args.arquivo.exists():
            logger.error("Arquivo não encontrado: %s", args.arquivo)
            sys.exit(1)
        total = processar_arquivo(args.arquivo)
    else:
        pasta = args.pasta or PASTA_PADRAO
        if not pasta.exists():
            logger.error("Pasta não encontrada: %s", pasta)
            sys.exit(1)
        total = processar_pasta(pasta)

    logger.info("=== Concluído: %d chunks indexados no total ===", total)


if __name__ == "__main__":
    main()
