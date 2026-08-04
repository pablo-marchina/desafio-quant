"""Limpeza/normalização + chunking semântico da KB (F3.2).

Segunda etapa do pipeline RAG (ARQUITETURA §4): pega os `KBDocument` da ingestão (F3.1) e
os quebra em `Chunk` — as unidades que serão embedadas pelo NeMo Retriever (F3.3), indexadas
no Qdrant (F3.4) e recuperadas com citação (F3.7). Puro/offline e determinístico (sem
rede/GPU, como a espinha verde dos nós F2 e a própria F3.1).

Decisões (F3.2):

- **Chunking semântico = por seção de markdown**, não por janela cega de N caracteres. Os
  snapshots curados (F3.1) já têm estrutura (`# título` + intro, depois `## seções`); cada
  seção é uma unidade coerente de significado, então vira um chunk. Isso mantém a fronteira
  do chunk alinhada à do conteúdo (um conceito por chunk) e evita cortar uma frase no meio.
- **Contexto de cabeçalho preservado** (`breadcrumb`): cada chunk carrega o caminho de
  títulos até ele (ex.: `("NVIDIA NIM…", "Capacidades")`). `contextual_text` prefixa esse
  caminho ao corpo — é o texto que a F3.3 deve embedar, para a recuperação de um trecho de
  bullets saber a que tecnologia/seção ele pertence. `text` fica puro (a citação fiel, F3.7).
- **Limpeza/normalização** (`normalize_text`): NFC, CRLF→LF, apara espaços à direita e
  colapsa linhas em branco repetidas. Estável a reformatações triviais. O `content_sha256`
  de cada chunk reusa o `content_hash` da F1.9 (mesma normalização de whitespace) → dedup e
  integridade no nível do chunk, como a evidência no nível da página.
- **Proveniência herdada**: o chunk carrega `url`/`tech`/`section`/`source_type`/`captured_at`
  do documento-pai, então cada chunk é **auto-suficiente** para indexar e citar — nenhuma
  afirmação recuperada sem fonte rastreável (§8).
- **Seção grande degrada graciosamente**: se uma seção excede `max_chars`, ela é repartida nas
  fronteiras de parágrafo (linha em branco), nunca no meio de uma frase; cada parte herda o
  mesmo `breadcrumb`. Os docs curados são pequenos, então quase tudo cabe em um chunk só.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field

from packages.scraping.provenance import content_hash

from .ingest import KBDocument, KBSection, KBSourceType, ingest

# Orçamento de caracteres de um chunk. Longo o bastante p/ uma seção curada caber inteira
# (um conceito por chunk), curto o bastante p/ caber com folga no contexto do embedder
# nv-embedqa (F3.3). Só seções acima disso são repartidas (por parágrafo).
DEFAULT_MAX_CHARS = 1200

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_BLANK_RUN = re.compile(r"\n{3,}")
_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")


def normalize_text(text: str) -> str:
    """Normaliza o texto curado antes do chunking — limpeza determinística e sem perda.

    Aplica NFC (forma canônica Unicode), troca CRLF/CR por LF, apara espaços à direita de
    cada linha e colapsa sequências de linhas em branco em uma só. Não remove conteúdo: só
    estabiliza a forma para o parsing de cabeçalhos e o hash ficarem reprodutíveis.
    """
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    collapsed = _BLANK_RUN.sub("\n\n", "\n".join(lines))
    return collapsed.strip()


class _Section(BaseModel):
    """Seção semântica intermediária (cabeçalho + corpo + caminho de títulos)."""

    model_config = ConfigDict(frozen=True)

    level: int
    heading: str | None
    breadcrumb: tuple[str, ...]
    body: str


class Chunk(BaseModel):
    """Unidade indexável da KB: um trecho semântico + proveniência herdada do documento.

    `text` é o corpo limpo do trecho (a citação fiel, F3.7); `contextual_text` prefixa o
    `breadcrumb` para a embeddagem (F3.3). `content_sha256` identifica o trecho (dedup no
    Qdrant, F3.4); `url`/`tech`/`section` tornam o chunk auto-suficiente para citar (§8).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: str = Field(description="ID estável e único: '<doc_id>::<índice>'.")
    doc_id: str = Field(description="ID do `KBDocument` de origem (F3.1).")
    index: int = Field(description="Ordem do chunk dentro do documento (0-based).")
    tech: str
    title: str = Field(description="Título do documento-pai.")
    url: str = Field(description="URL canônica da fonte — proveniência citável (§8).")
    section: KBSection
    source_type: KBSourceType
    heading: str | None = Field(description="Cabeçalho imediato do trecho (None se preâmbulo).")
    breadcrumb: tuple[str, ...] = Field(description="Caminho de títulos do doc até este trecho.")
    text: str = Field(description="Corpo limpo do trecho (citação fiel).")
    content_sha256: str
    char_count: int

    @property
    def contextual_text(self) -> str:
        """Texto a embedar (F3.3): caminho de títulos + corpo, para o trecho saber seu contexto."""
        if not self.breadcrumb:
            return self.text
        return " > ".join(self.breadcrumb) + "\n\n" + self.text


def _split_sections(text: str) -> list[_Section]:
    """Quebra o markdown normalizado em seções, rastreando o caminho de títulos (breadcrumb)."""
    sections: list[_Section] = []
    ancestors: dict[int, str] = {}
    level, heading, breadcrumb, body = 0, None, (), []

    def flush() -> None:
        joined = "\n".join(body).strip()
        if heading is None and not joined:
            return  # preâmbulo vazio (texto começa direto no `#`) — nada a emitir
        sections.append(
            _Section(level=level, heading=heading, breadcrumb=breadcrumb, body=joined)
        )

    for line in text.split("\n"):
        match = _HEADING.match(line)
        if match:
            flush()
            level = len(match.group(1))
            heading = match.group(2).strip()
            for deeper in [lvl for lvl in ancestors if lvl >= level]:
                del ancestors[deeper]
            ancestors[level] = heading
            breadcrumb = tuple(ancestors[lvl] for lvl in sorted(ancestors))
            body = []
        else:
            body.append(line)
    flush()
    return sections


def _pack_body(body: str, max_chars: int) -> list[str]:
    """Reparte um corpo de seção em fronteiras de parágrafo, empacotando até `max_chars`.

    Mantém parágrafos inteiros juntos (não corta frase no meio); um único parágrafo maior que
    o orçamento segue inteiro (degradação graciosa). Quase sempre devolve uma parte só.
    """
    paragraphs = [p.strip() for p in _PARAGRAPH_SPLIT.split(body) if p.strip()]
    if not paragraphs:
        return []

    parts: list[str] = []
    current: list[str] = []
    size = 0
    for paragraph in paragraphs:
        addition = len(paragraph) + (2 if current else 0)
        if current and size + addition > max_chars:
            parts.append("\n\n".join(current))
            current, size = [], 0
            addition = len(paragraph)
        current.append(paragraph)
        size += addition
    if current:
        parts.append("\n\n".join(current))
    return parts


def chunk_document(doc: KBDocument, *, max_chars: int = DEFAULT_MAX_CHARS) -> tuple[Chunk, ...]:
    """Quebra um `KBDocument` (F3.1) em chunks semânticos por seção de markdown.

    Normaliza o texto, separa por cabeçalho e emite um `Chunk` por seção (repartindo só as
    seções acima de `max_chars`). Cada chunk herda a proveniência do doc e ganha `breadcrumb`,
    hash próprio e índice estável. Determinístico: o mesmo doc gera os mesmos chunks/IDs.
    """
    normalized = normalize_text(doc.text)
    chunks: list[Chunk] = []
    for section in _split_sections(normalized):
        for body_part in _pack_body(section.body, max_chars):
            index = len(chunks)
            chunks.append(
                Chunk(
                    chunk_id=f"{doc.id}::{index:02d}",
                    doc_id=doc.id,
                    index=index,
                    tech=doc.tech,
                    title=doc.title,
                    url=doc.url,
                    section=doc.section,
                    source_type=doc.source_type,
                    heading=section.heading,
                    breadcrumb=section.breadcrumb,
                    text=body_part,
                    content_sha256=content_hash(body_part),
                    char_count=len(body_part),
                )
            )
    return tuple(chunks)


def chunk_documents(
    docs: Iterable[KBDocument], *, max_chars: int = DEFAULT_MAX_CHARS
) -> tuple[Chunk, ...]:
    """Chunkifica vários documentos preservando a ordem (achata os chunks de cada doc)."""
    out: list[Chunk] = []
    for doc in docs:
        out.extend(chunk_document(doc, max_chars=max_chars))
    return tuple(out)


def chunk_kb(*, max_chars: int = DEFAULT_MAX_CHARS) -> tuple[Chunk, ...]:
    """Pipeline F3.1→F3.2: ingere o manifesto inteiro e devolve todos os chunks da KB."""
    return chunk_documents(ingest(), max_chars=max_chars)


__all__ = [
    "DEFAULT_MAX_CHARS",
    "Chunk",
    "normalize_text",
    "chunk_document",
    "chunk_documents",
    "chunk_kb",
]
