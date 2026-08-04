from __future__ import annotations

from typing import Any

import trafilatura

from radar.rag.retriever import get_store

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

SEED_URL_PREFIXES: set[str] = {
    "https://www.nvidia.com/en-us/startups/",
    "https://www.nvidia.com/en-us/ai-data-science/products/nim-microservices/",
    "https://www.nvidia.com/en-us/ai-data-science/products/nemo/",
    "https://github.com/NVIDIA/NeMo-Guardrails",
    "https://developer.nvidia.com/triton-inference-server",
    "https://github.com/NVIDIA/TensorRT-LLM",
    "https://rapids.ai/",
    "https://docs.rapids.ai/api/cudf/stable/",
    "https://docs.rapids.ai/api/cuml/stable/",
    "https://developer.nvidia.com/cuda-zone",
    "https://developer.nvidia.com/riva",
    "https://www.nvidia.com/en-us/omniverse/",
    "https://developer.nvidia.com/isaac",
    "https://www.nvidia.com/en-us/clara/",
    "https://www.nvidia.com/en-us/ai-data-science/products/morpheus/",
    "https://www.nvidia.com/en-us/data-center/products/ai-enterprise/",
}

NVIDIA_DOC_URLS: list[str] = [
    "https://docs.nvidia.com/deeplearning/nim/large-language-models/latest/index.html",
    "https://docs.nvidia.com/deeplearning/tensorrt/latest/index.html",
    "https://docs.nvidia.com/deeplearning/nemo/latest/index.html",
    "https://docs.nvidia.com/deeplearning/trt-llm/latest/index.html",
    "https://docs.nvidia.com/deeplearning/cudf/latest/index.html",
    "https://docs.nvidia.com/cuda/latest/index.html",
    "https://docs.nvidia.com/riva/latest/index.html",
    "https://docs.nvidia.com/omniverse/latest/index.html",
    "https://docs.nvidia.com/isaac/latest/index.html",
    "https://docs.nvidia.com/clara/latest/index.html",
    "https://docs.nvidia.com/ai-enterprise/latest/index.html",
    "https://docs.nvidia.com/rapids/latest/index.html",
    "https://docs.rapids.ai/api/cuml/latest/",
    "https://docs.nvidia.com/morpheus/latest/index.html",
]

_next_id = 1000


def _next_chunk_id() -> int:
    global _next_id
    _next_id += 1
    return _next_id


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    if not text:
        return []
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 1 <= chunk_size:
            current = (current + "\n\n" + para).strip()
        else:
            if current:
                chunks.append(current)
            current = para
    if current:
        chunks.append(current)

    if overlap > 0 and len(chunks) > 1:
        merged: list[str] = []
        for i, chunk in enumerate(chunks):
            if i > 0:
                prev_tail = chunks[i - 1][-overlap:]
                chunk = prev_tail + "\n" + chunk
            merged.append(chunk)
        return merged

    return chunks


def fetch_doc_text(url: str, timeout: int = 15) -> str:
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        return ""
    text = trafilatura.extract(downloaded, output_format="txt", include_links=False)
    return text or ""


def _resolve_chunk_technology(url: str) -> str:
    tech_map: dict[str, str] = {
        "nim": "NVIDIA NIM",
        "tensorrt": "TensorRT-LLM",
        "nemo": "NVIDIA NeMo",
        "guardrails": "NeMo Guardrails",
        "triton": "NVIDIA Triton Inference Server",
        "cudf": "cuDF",
        "cuml": "cuML",
        "rapids": "NVIDIA RAPIDS",
        "cuda": "CUDA",
        "riva": "NVIDIA Riva",
        "omniverse": "NVIDIA Omniverse",
        "isaac": "NVIDIA Isaac",
        "clara": "NVIDIA Clara",
        "morpheus": "NVIDIA Morpheus",
        "inception": "NVIDIA Inception",
        "enterprise": "NVIDIA AI Enterprise",
    }
    url_lower = url.lower()
    for key, tech in tech_map.items():
        if key in url_lower:
            return tech
    return "NVIDIA AI Enterprise"


def enrich_from_urls(urls: list[str] | None = None, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> dict[str, Any]:
    store = get_store()
    existing_urls = set(SEED_URL_PREFIXES)

    inserted: list[str] = []
    skipped: list[str] = []
    errors: list[dict[str, str]] = []

    if urls is None:
        urls = NVIDIA_DOC_URLS

    for url in urls:
        if url in existing_urls:
            skipped.append(url)
            continue

        text = fetch_doc_text(url, timeout=15)
        if not text:
            errors.append({"url": url, "error": "empty or failed fetch"})
            continue

        chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        technology = _resolve_chunk_technology(url)

        doc_chunks = []
        for i, chunk_content in enumerate(chunks):
            chunk_id = _next_chunk_id()
            doc_chunks.append({
                "id": chunk_id,
                "url": url,
                "technology": technology,
                "title": f"{technology} — Doc chunk {i + 1}",
                "content": chunk_content,
            })

        store.insert(doc_chunks)
        inserted.append(url)

    return {
        "urls_provided": len(urls),
        "inserted": len(inserted),
        "skipped": len(skipped),
        "errors": errors,
        "inserted_urls": inserted,
        "skipped_urls": skipped,
    }


def enrich_nvidia_docs(chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> dict[str, Any]:
    return enrich_from_urls(chunk_size=chunk_size, overlap=overlap)
