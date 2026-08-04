"""Passo 3.5 — Ingestão da Base de Conhecimento NVIDIA no Qdrant.

Baixa o conteúdo textual das URLs oficiais NVIDIA, gera chunks com
RecursiveCharacterTextSplitter, vetoriza com all-MiniLM-L6-v2 e armazena
na collection `nvidia_tech_knowledge` do Qdrant.

Uso:
  python ingest_nvidia_docs.py --dry-run         # lista URLs sem escrever
  python ingest_nvidia_docs.py --limit-urls 2    # teste com 2 URLs
  python ingest_nvidia_docs.py                   # rodada completa (18 URLs)
  python ingest_nvidia_docs.py --force           # reprocessa tudo
"""
from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import torch
import trafilatura
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PayloadSchemaType, PointStruct, VectorParams

from src.config import get_settings
from src.logging_conf import get_logger, setup_logging
from src.phase2.tools.extractor import _fetch_html
from src.enrichment.spa_fallback import _fetch_with_crawl4ai

setup_logging()
logger = get_logger("ingest.nvidia")

COLLECTION = "nvidia_tech_knowledge"
VECTOR_SIZE = 384
STATE_FILE = Path("nvidia_ingest_state.json")

SOURCES: list[dict] = [
    {"tech": "NVIDIA Inception",     "cat": "Programa",    "url": "https://www.nvidia.com/en-us/startups/"},
    {"tech": "NVIDIA NIM",           "cat": "Inferência",  "url": "https://www.nvidia.com/en-us/ai-data-science/products/nim-microservices/"},
    {"tech": "NVIDIA API Catalog",   "cat": "Inferência",  "url": "https://build.nvidia.com/"},
    {"tech": "NVIDIA NeMo",          "cat": "Modelos",     "url": "https://www.nvidia.com/en-us/ai-data-science/products/nemo/"},
    {"tech": "NeMo Guardrails",      "cat": "Modelos",     "url": "https://github.com/NVIDIA/NeMo-Guardrails"},
    {"tech": "NVIDIA Triton",        "cat": "Inferência",  "url": "https://developer.nvidia.com/triton-inference-server"},
    {"tech": "Triton Docs",          "cat": "Inferência",  "url": "https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/"},
    {"tech": "TensorRT-LLM",         "cat": "Inferência",  "url": "https://github.com/NVIDIA/TensorRT-LLM"},
    {"tech": "NVIDIA RAPIDS",        "cat": "Dados",       "url": "https://rapids.ai/"},
    {"tech": "cuDF",                 "cat": "Dados",       "url": "https://docs.rapids.ai/api/cudf/stable/"},
    {"tech": "cuML",                 "cat": "Dados",       "url": "https://docs.rapids.ai/api/cuml/stable/"},
    {"tech": "CUDA Toolkit",         "cat": "Programação", "url": "https://developer.nvidia.com/cuda-toolkit"},
    {"tech": "NVIDIA Riva",          "cat": "Voz",         "url": "https://developer.nvidia.com/riva"},
    {"tech": "NVIDIA Omniverse",     "cat": "Simulação",   "url": "https://www.nvidia.com/en-us/omniverse/"},
    {"tech": "NVIDIA Isaac",         "cat": "Robótica",    "url": "https://developer.nvidia.com/isaac"},
    {"tech": "NVIDIA Clara",         "cat": "Saúde",       "url": "https://www.nvidia.com/en-us/clara/"},
    {"tech": "NVIDIA Morpheus",      "cat": "Segurança",   "url": "https://developer.nvidia.com/morpheus-cybersecurity"},
    {"tech": "NVIDIA AI Enterprise", "cat": "Empresarial", "url": "https://www.nvidia.com/en-us/data-center/products/ai-enterprise/"},
]


# =============================================================================
# Estado persistente
# =============================================================================

def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"processed_urls": {}, "total_chunks": 0}


def _save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


# =============================================================================
# Qdrant
# =============================================================================

async def _ensure_collection(client: AsyncQdrantClient) -> None:
    existing = {c.name for c in (await client.get_collections()).collections}
    if COLLECTION in existing:
        logger.info("Collection '%s' já existe.", COLLECTION)
        return
    await client.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )
    for field, schema in [
        ("tech_name",  PayloadSchemaType.KEYWORD),
        ("category",   PayloadSchemaType.KEYWORD),
        ("source_url", PayloadSchemaType.KEYWORD),
    ]:
        await client.create_payload_index(
            collection_name=COLLECTION,
            field_name=field,
            field_schema=schema,
        )
    logger.info("Collection '%s' criada com indexes em tech_name, category, source_url.", COLLECTION)


def _make_point(tech: str, cat: str, url: str, text: str, embedding, idx: int) -> PointStruct:
    point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{tech}_{idx}"))
    return PointStruct(
        id=point_id,
        vector=embedding.tolist(),
        payload={
            "tech_name": tech,
            "category": cat,
            "source_url": url,
            "text": text,
            "chunk_index": idx,
        },
    )


# =============================================================================
# Fetch + extração
# =============================================================================

async def _fetch_content(url: str) -> str | None:
    # GitHub → tenta raw README em main, depois master (fail-soft se ambos falharem)
    if "github.com" in url:
        path_parts = url.rstrip("/").split("github.com/")[-1].split("/")[:2]
        owner_repo = "/".join(path_parts)
        for branch in ("main", "master"):
            raw_url = f"https://raw.githubusercontent.com/{owner_repo}/{branch}/README.md"
            content = await _fetch_html(raw_url)
            if content and len(content) > 200:
                logger.debug("GitHub README obtido via branch '%s': %s", branch, url)
                return content
        logger.warning("GitHub README não encontrado para %s — pulando.", url)
        return None

    # HTML normal → trafilatura
    html = await _fetch_html(url)
    text: str | None = None
    if html:
        text = trafilatura.extract(html, include_comments=False, include_tables=True)

    # SPA detection → Crawl4AI fallback
    spa_signals = not text or len(text) < 200 or "enable javascript" in (text or "").lower()
    if spa_signals:
        logger.warning("SPA detectado em %s — ativando Crawl4AI.", url)
        text = await _fetch_with_crawl4ai(url)

    return text or None


# =============================================================================
# CLI
# =============================================================================

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Ingere documentação NVIDIA no Qdrant.")
    p.add_argument("--dry-run",    action="store_true", help="Lista URLs sem escrever.")
    p.add_argument("--force",      action="store_true", help="Reprocessa URLs já ingeridas.")
    p.add_argument("--batch-size", type=int, default=32, help="Chunks por encode (padrão: 32).")
    p.add_argument("--limit-urls", type=int, default=None, help="Processa apenas as primeiras N URLs.")
    return p.parse_args()


# =============================================================================
# Main
# =============================================================================

async def main() -> None:
    args = _parse_args()
    settings = get_settings()
    state = _load_state()

    # Filtra fontes
    sources = SOURCES[: args.limit_urls] if args.limit_urls else SOURCES
    pending = [
        s for s in sources
        if args.force or s["url"] not in state["processed_urls"]
    ]
    already_done = [s for s in sources if s not in pending]

    print(f"📚 Carregando {len(sources)} URLs da NVIDIA para ingestão...")
    for s in already_done:
        n = state["processed_urls"][s["url"]]["chunks"]
        print(f"⏭️  URL já processada: {s['url']} ({n} chunks)")

    if args.dry_run:
        print(f"\n[DRY-RUN] {len(pending)} URL(s) seriam processadas:")
        for s in pending:
            print(f"  • {s['tech']} ({s['cat']}) — {s['url']}")
        return

    if not pending:
        print("Nenhuma URL pendente. Use --force para reprocessar.")
        return

    # Modelo (carregado uma única vez)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info("Carregando modelo '%s' em device='%s'...", settings.sbert_model, device)
    model = SentenceTransformer(settings.sbert_model, device=device)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", ".", " ", ""],
    )

    qdrant = AsyncQdrantClient(
        host=settings.qdrant_host, port=settings.qdrant_port, check_compatibility=False
    )
    await _ensure_collection(qdrant)

    total_ingested = 0

    for source in pending:
        tech = source["tech"]
        cat  = source["cat"]
        url  = source["url"]

        print(f"\n🔄 Processando: {tech} ({cat}) — {url}")

        text = await _fetch_content(url)
        if not text:
            logger.error("Sem conteúdo extraído para %s — pulando.", tech)
            continue

        chunks = splitter.split_text(text)
        if not chunks:
            logger.warning("%s: nenhum chunk gerado — pulando.", tech)
            continue
        print(f"📄 {tech}: {len(chunks)} chunks gerados")

        # Encode em lote (sem bloquear o event loop)
        all_texts = chunks
        embeddings = await asyncio.to_thread(
            model.encode,
            all_texts,
            batch_size=args.batch_size,
            convert_to_tensor=False,
            show_progress_bar=False,
        )

        points = [
            _make_point(tech, cat, url, chunk, emb, i)
            for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
        ]

        try:
            await qdrant.upsert(collection_name=COLLECTION, points=points, wait=True)
        except Exception as exc:
            logger.error("Falha no upsert para %s: %s — pulando.", tech, exc)
            continue

        print(f"✅ {len(points)} chunks ingeridos para {tech}")
        total_ingested += len(points)

        # Atualiza estado após cada URL (retomável se interrompido)
        state["processed_urls"][url] = {
            "chunks": len(points),
            "last_processed": datetime.now(timezone.utc).isoformat(),
        }
        state["total_chunks"] = sum(v["chunks"] for v in state["processed_urls"].values())
        _save_state(state)

    await qdrant.close()
    print(f"\n🎉 Ingestão da base NVIDIA concluída! Total de chunks: {total_ingested}.")


if __name__ == "__main__":
    asyncio.run(main())
