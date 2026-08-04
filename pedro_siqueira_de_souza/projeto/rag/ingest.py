"""Ingestão da base de conhecimento NVIDIA — primeira estação do RAG (Entregável 3).

O RAG precisa de matéria-prima limpa para indexar. Este módulo percorre as
páginas oficiais das tecnologias NVIDIA (lista `NVIDIA_SOURCES`), baixa cada
uma e extrai o TEXTO PRINCIPAL com trafilatura — descartando menu, rodapé e
boilerplate. O resultado é gravado num `.jsonl` (`rag/corpus/nvidia_docs.jsonl`)
que o próximo passo (chunking + embeddings + Qdrant) lê SEM precisar re-scrapear.

Decisões de design (mesmas disciplinas do resto do repo):
  - Reusa a "costura" de fetch (`scraping.fetch.fetch_static`) em vez de chamar
    HTTP direto: centraliza o tratamento de erro e deixa os testes trocarem a
    rede por HTML salvo via `monkeypatch` (ver tests/test_enricher.py).
  - `fetch_static` (HTTP puro) é o fetcher mais barato. Algumas páginas da
    NVIDIA são SPA pesadas em JS e podem render pouco conteúdo por essa via —
    elas caem como "não ingeridas" e ficam para um passo futuro (DynamicFetcher).
  - Erro POR FONTE: uma página fora do ar ou sem texto aproveitável vira `None`
    e é registrada, sem derrubar a ingestão das demais.
  - Saída em JSONL (um doc por linha): fácil de inspecionar, versionar e
    alimentar o indexador depois.
"""
import json
from pathlib import Path

import trafilatura
from loguru import logger
from pydantic import BaseModel

from scraping.fetch import ScrapeError, fetch_static

# Diretório onde o corpus extraído é gravado (lido pelo passo de indexação).
CORPUS_DIR = Path(__file__).parent / "corpus"
CORPUS_PATH = CORPUS_DIR / "nvidia_docs.jsonl"


class NvidiaSource(BaseModel):
    """Uma página oficial a ingerir: o nome da tecnologia + a URL."""

    tech: str
    url: str


class NvidiaDoc(BaseModel):
    """Documento já extraído e limpo, pronto para chunking/embeddings."""

    tech: str
    url: str
    text: str

    @property
    def char_count(self) -> int:
        return len(self.text)


# Fonte da verdade da base NVIDIA (brief §Base de conhecimento + artefatos/ux.md §8.2).
# Cada entrada vira (na melhor das hipóteses) um NvidiaDoc no corpus.
NVIDIA_SOURCES: list[NvidiaSource] = [
    NvidiaSource(tech="NVIDIA Inception", url="https://www.nvidia.com/en-us/startups/"),
    NvidiaSource(tech="NVIDIA NIM", url="https://www.nvidia.com/en-us/ai-data-science/products/nim-microservices/"),
    NvidiaSource(tech="NVIDIA API Catalog", url="https://build.nvidia.com/"),
    NvidiaSource(tech="NVIDIA NeMo", url="https://www.nvidia.com/en-us/ai-data-science/products/nemo/"),
    NvidiaSource(tech="NeMo Guardrails", url="https://github.com/NVIDIA/NeMo-Guardrails"),
    NvidiaSource(tech="Triton Inference Server", url="https://developer.nvidia.com/triton-inference-server"),
    NvidiaSource(tech="Triton docs", url="https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/"),
    NvidiaSource(tech="TensorRT-LLM", url="https://github.com/NVIDIA/TensorRT-LLM"),
    NvidiaSource(tech="NVIDIA RAPIDS", url="https://rapids.ai/"),
    NvidiaSource(tech="cuDF", url="https://docs.rapids.ai/api/cudf/stable/"),
    NvidiaSource(tech="cuML", url="https://docs.rapids.ai/api/cuml/stable/"),
    NvidiaSource(tech="CUDA Toolkit", url="https://developer.nvidia.com/cuda-toolkit"),
    NvidiaSource(tech="NVIDIA Riva", url="https://developer.nvidia.com/riva"),
    NvidiaSource(tech="NVIDIA Omniverse", url="https://www.nvidia.com/en-us/omniverse/"),
    NvidiaSource(tech="NVIDIA Isaac", url="https://developer.nvidia.com/isaac"),
    NvidiaSource(tech="NVIDIA Clara", url="https://www.nvidia.com/en-us/clara/"),
    NvidiaSource(tech="NVIDIA Morpheus", url="https://developer.nvidia.com/morpheus-cybersecurity"),
    NvidiaSource(tech="NVIDIA AI Enterprise", url="https://www.nvidia.com/en-us/data-center/products/ai-enterprise/"),
]

# Páginas com menos texto que isto são tratadas como "não aproveitáveis" por
# enquanto (provável SPA que não renderizou sem JS). Limiar baixo de propósito:
# é só um filtro de páginas vazias, não de qualidade.
MIN_CHARS = 200


def ingest_source(source: NvidiaSource) -> NvidiaDoc | None:
    """Baixa e extrai o texto principal de UMA fonte. None se falhar/vier vazio."""
    try:
        html = fetch_static(source.url).html_content
    except ScrapeError:
        logger.warning("ingest: falha de rede em {} ({})", source.tech, source.url)
        return None

    # trafilatura devolve None quando não acha conteúdo principal aproveitável.
    text = trafilatura.extract(html)
    if not text or len(text) < MIN_CHARS:
        logger.warning(
            "ingest: conteúdo insuficiente em {} ({} chars) — provável SPA/JS",
            source.tech,
            len(text or ""),
        )
        return None

    logger.info("ingest: {} OK ({} chars)", source.tech, len(text))
    return NvidiaDoc(tech=source.tech, url=source.url, text=text)


def ingest_all(sources: list[NvidiaSource] | None = None) -> list[NvidiaDoc]:
    """Ingere todas as fontes. Erro por fonte não derruba as demais."""
    sources = sources if sources is not None else NVIDIA_SOURCES
    docs: list[NvidiaDoc] = []
    for source in sources:
        doc = ingest_source(source)
        if doc is not None:
            docs.append(doc)
    return docs


def save_corpus(docs: list[NvidiaDoc], path: Path = CORPUS_PATH) -> Path:
    """Grava os docs como JSONL (um por linha). Cria o diretório se faltar."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc.model_dump(), ensure_ascii=False) + "\n")
    logger.info("ingest: corpus salvo em {} ({} docs)", path, len(docs))
    return path


def _print_relatorio(sources: list[NvidiaSource], docs: list[NvidiaDoc]) -> None:
    """Imprime quais referências entraram no corpus e quais ficaram de fora."""
    ok_techs = {d.tech for d in docs}
    print("\n=== Ingestão da base NVIDIA ===")
    print(f"Utilizadas: {len(docs)}/{len(sources)}\n")
    print("[OK] Conseguimos utilizar:")
    for d in docs:
        print(f"  - {d.tech} ({d.char_count} chars) — {d.url}")
    faltando = [s for s in sources if s.tech not in ok_techs]
    print("\n[--] Não utilizadas por enquanto:")
    for s in faltando:
        print(f"  - {s.tech} — {s.url}")


if __name__ == "__main__":
    # Execução manual — exige acesso à rede (baixa páginas reais da NVIDIA).
    documentos = ingest_all()
    save_corpus(documentos)
    _print_relatorio(NVIDIA_SOURCES, documentos)
