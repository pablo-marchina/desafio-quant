"""Ingestão da base de conhecimento NVIDIA (F3.1).

Primeira etapa do pipeline RAG (ARQUITETURA §4): traz as fontes do §10 do brief para
`data/knowledge_base/` e as carrega num documento tipado (`KBDocument`), pronto para o
chunking semântico (F3.2) -> embeddings NeMo Retriever (F3.3) -> Qdrant (F3.4).

Decisões (F3.1):

- **Manifesto + conteúdo separados**, espelhando as seeds do §9 (`data/seeds/*.yaml` +
  `packages/scraping/seeds.py`): `data/knowledge_base/sources.yaml` é a fonte única dos
  metadados (id, tech, url oficial, seção, tipo); `docs/<id>.md` carrega só o texto. Sem
  duplicação => sem drift.
- **Offline e reproduzível** (sem rede/credencial/GPU, como a espinha verde dos nós F2): o
  conteúdo é um snapshot **curado** de cada página oficial, citável pela `url` do manifesto.
  O *refresh* ao vivo das páginas (coleta via adapters F1) é hook de rede futuro — a `url`
  canônica e `captured_at` ficam no manifesto para sustentá-lo.
- **Proveniência (§8):** cada documento carrega `content_sha256` (reusa `content_hash` da
  evidência, F1.9) + a `url` da fonte — nenhuma afirmação sem fonte rastreável.
- **Escopo desta task:** §10.2 (documentações oficiais). Tasks vizinhas só ADICIONAM entradas
  ao manifesto, sem tocar este loader (os tipos já estão previstos em `KBSourceType`): vídeos
  transcritos do §10.1 (F3.1b, `video_transcript`), MONAI (F3.1c, `doc`), materiais AI-native
  do §10.1 (F3.1d, `grounding`).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from packages.scraping.provenance import content_hash

# data/knowledge_base/ na raiz do repo (packages/rag/ingest.py -> parents[2] == raiz).
KB_DIR = Path(__file__).resolve().parents[2] / "data" / "knowledge_base"
MANIFEST = KB_DIR / "sources.yaml"

# Subseções do §10 e tipos de fonte. `doc` (§10.2, esta task); `blog`, `video_transcript` e
# `grounding` são hooks declarados p/ F3.1b/F3.1d não precisarem reabrir o loader.
KBSection = Literal["10.1", "10.2"]
KBSourceType = Literal["doc", "blog", "video_transcript", "grounding"]


class KBSource(BaseModel):
    """Entrada do manifesto: uma fonte do §10 + ponteiro para seu conteúdo curado."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(description="Slug estável e único.")
    tech: str = Field(description="Tecnologia NVIDIA canônica (ex.: 'NVIDIA NIM').")
    title: str
    url: str = Field(description="URL oficial da fonte (§10).")
    section: KBSection = Field(description="Subseção do §10 (10.1 materiais · 10.2 docs).")
    source_type: KBSourceType = "doc"
    path: str = Field(description="Caminho do conteúdo curado, relativo à raiz da KB.")
    captured_at: date = Field(description="Data do snapshot curado (proveniência).")
    access: str = Field(description="Nota de acesso/licença da fonte.")
    notes: str = ""

    @property
    def content_path(self) -> Path:
        """Caminho absoluto do `.md` de conteúdo desta fonte."""
        return KB_DIR / self.path


class KBDocument(BaseModel):
    """Documento ingerido: metadados da fonte + texto + proveniência (pré-chunk F3.2)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    tech: str
    title: str
    url: str
    section: KBSection
    source_type: KBSourceType
    captured_at: date
    text: str
    content_sha256: str
    char_count: int


@lru_cache
def load_kb_sources() -> tuple[KBSource, ...]:
    """Fontes do §10 declaradas no manifesto (cacheado). Valida estrutura e unicidade.

    Levanta `ValueError`/`ValidationError` se o manifesto estiver ausente, vazio, com `url`
    não-http ou com `id` duplicado — falha cedo e barulhento, como `seeds.load_sources`.
    """
    if not MANIFEST.is_file():
        raise ValueError(f"manifesto da KB ausente: {MANIFEST}")
    data = yaml.safe_load(MANIFEST.read_text(encoding="utf-8")) or {}
    raw_sources = data.get("sources") or []
    if not raw_sources:
        raise ValueError(f"manifesto da KB sem fontes: {MANIFEST}")

    sources: list[KBSource] = []
    seen: set[str] = set()
    for raw in raw_sources:
        src = KBSource.model_validate(raw)
        if not src.url.startswith("http"):
            raise ValueError(f"{src.id!r}: url não-http: {src.url!r}")
        if src.id in seen:
            raise ValueError(f"id de fonte duplicado na KB: {src.id!r}")
        seen.add(src.id)
        sources.append(src)
    return tuple(sources)


def ingest(sources: Iterable[KBSource] | None = None) -> tuple[KBDocument, ...]:
    """Carrega o conteúdo curado de cada fonte -> `KBDocument` com proveniência.

    Lê o `.md` de cada fonte, calcula `content_sha256` (mesma normalização da evidência,
    F1.9) e devolve documentos tipados, prontos para o chunking (F3.2). Determinístico e
    offline. Levanta `ValueError` se um conteúdo estiver ausente ou vazio (nada a indexar).
    `sources=None` usa o manifesto inteiro; passe um subconjunto para ingerir parcialmente.
    """
    items = tuple(sources) if sources is not None else load_kb_sources()
    docs: list[KBDocument] = []
    for src in items:
        path = src.content_path
        if not path.is_file():
            raise ValueError(f"{src.id!r}: conteúdo ausente em {path}")
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            raise ValueError(f"{src.id!r}: conteúdo vazio em {path}")
        docs.append(
            KBDocument(
                id=src.id,
                tech=src.tech,
                title=src.title,
                url=src.url,
                section=src.section,
                source_type=src.source_type,
                captured_at=src.captured_at,
                text=text,
                content_sha256=content_hash(text),
                char_count=len(text),
            )
        )
    return tuple(docs)


def covered_techs(docs: Iterable[KBDocument] | None = None) -> frozenset[str]:
    """Conjunto de techs presentes na KB — base da cobertura por tech (F3.8)."""
    items = tuple(docs) if docs is not None else ingest()
    return frozenset(d.tech for d in items)


__all__ = [
    "KB_DIR",
    "MANIFEST",
    "KBSection",
    "KBSourceType",
    "KBSource",
    "KBDocument",
    "load_kb_sources",
    "ingest",
    "covered_techs",
]
