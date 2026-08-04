"""Testes da limpeza/normalização + chunking semântico da KB (F3.2).

Garantem que `normalize_text` limpa de forma determinística e sem perda, que o chunking
respeita as fronteiras de seção do markdown (um conceito por chunk), que cada chunk carrega
proveniência auto-suficiente (url/tech/hash/breadcrumb) e que seções grandes degradam por
parágrafo. Cobre o pipeline F3.1→F3.2 sobre a KB real (offline, sem rede/GPU).
"""

from __future__ import annotations

from datetime import date

from packages.rag import Chunk, chunk_document, chunk_kb, ingest, normalize_text
from packages.rag.chunk import _split_sections
from packages.rag.ingest import KBDocument
from packages.scraping.provenance import content_hash

DOC = """# Título do Doc

Parágrafo de introdução.

## Capacidades
- bullet um
- bullet dois

## Quando recomendar
Texto da segunda seção.
"""


def test_normalize_is_lossless_and_deterministic() -> None:
    messy = "# T\r\n\r\n\r\nlinha com espaço à direita   \n\n\n\nfim   "
    clean = normalize_text(messy)
    assert "\r" not in clean  # CRLF/CR -> LF
    assert "   \n" not in clean  # sem espaço à direita
    assert "\n\n\n" not in clean  # linhas em branco colapsadas
    assert clean == clean.strip()
    assert normalize_text(clean) == clean  # idempotente


def test_chunks_split_on_markdown_sections() -> None:
    chunks = chunk_document(_doc_from_text("kb-fixo", DOC))
    assert chunks and all(isinstance(c, Chunk) for c in chunks)
    # A intro do H1 e cada H2 viram chunks distintos (um conceito por chunk).
    headings = [c.heading for c in chunks]
    assert headings == ["Título do Doc", "Capacidades", "Quando recomendar"]
    assert chunks[0].text == "Parágrafo de introdução."  # lede sob o H1, sem os H2


def test_real_kb_docs_yield_a_lede_chunk_each() -> None:
    # Sobre a KB real: todo doc rende ≥1 chunk e o primeiro é a lede sob o H1 (breadcrumb=1).
    for doc in ingest():
        chunks = chunk_document(doc)
        assert chunks, f"{doc.id} não gerou chunk"
        assert len(chunks[0].breadcrumb) == 1
        assert all(c.doc_id == doc.id for c in chunks)


def test_breadcrumb_carries_heading_context() -> None:
    chunks = chunk_document(_doc_from_text("kb-fixo", DOC))
    capac = next(c for c in chunks if c.heading == "Capacidades")
    assert capac.breadcrumb == ("Título do Doc", "Capacidades")
    # contextual_text (o que a F3.3 embeda) prefixa o caminho de títulos ao corpo.
    assert capac.contextual_text.startswith("Título do Doc > Capacidades")
    assert "bullet um" in capac.contextual_text
    assert capac.text == "- bullet um\n- bullet dois"  # `text` puro, sem o breadcrumb


def test_each_chunk_is_self_sufficient_provenance() -> None:
    for chunk in chunk_kb():
        assert chunk.text.strip()  # nada vazio é indexado
        assert chunk.url.startswith("http")  # toda recuperação tem fonte citável (§8)
        assert chunk.tech  # herda a tech do doc-pai (base p/ cobertura F3.8)
        assert chunk.content_sha256 == content_hash(chunk.text)
        assert chunk.char_count == len(chunk.text)
        assert chunk.chunk_id == f"{chunk.doc_id}::{chunk.index:02d}"


def test_chunk_ids_are_unique_and_stable() -> None:
    first = [c.chunk_id for c in chunk_kb()]
    second = [c.chunk_id for c in chunk_kb()]
    assert first == second  # determinístico entre runs
    assert len(first) == len(set(first))  # IDs únicos em toda a KB


def test_large_section_splits_on_paragraph_boundaries() -> None:
    big = "# T\n\nintro\n\n## S\n\n" + "\n\n".join(f"paragrafo {i} xxxxxxxxxx" for i in range(20))
    chunks = chunk_document(_doc_from_text("kb-grande", big), max_chars=120)
    parts = [c for c in chunks if c.heading == "S"]
    assert len(parts) > 1  # seção grande repartida
    assert all(c.breadcrumb == ("T", "S") for c in parts)  # mesmo contexto nas partes
    assert all(c.char_count <= 120 or "\n\n" not in c.text for c in parts)  # nunca corta no meio


def test_preamble_before_h1_is_not_emitted_empty() -> None:
    # Texto que começa com linhas em branco não vira um chunk de preâmbulo vazio.
    sections = _split_sections(normalize_text("\n\n# T\n\ncorpo"))
    assert [s.heading for s in sections] == ["T"]


def _doc_from_text(doc_id: str, text: str) -> KBDocument:
    """Constrói um `KBDocument` mínimo a partir de texto cru (fixture local, sem tocar a KB)."""
    return KBDocument(
        id=doc_id,
        tech="Tech Fixture",
        title="Fixture",
        url="https://example.com",
        section="10.2",
        source_type="doc",
        captured_at=date(2026, 6, 7),
        text=text,
        content_sha256=content_hash(text),
        char_count=len(text),
    )
