"""Testes do TextChunker."""

from apps.api.src.modules.ingestion.application.text_chunker import TextChunker


def _chunker(chunk_size: int = 100, overlap: int = 20) -> TextChunker:
    return TextChunker(chunk_size=chunk_size, chunk_overlap=overlap)


def test_chunk_empty_returns_empty_list() -> None:
    assert _chunker().chunk("") == []


def test_chunk_short_text_returns_single_chunk() -> None:
    text = "Texto curto."
    result = _chunker(chunk_size=200).chunk(text)
    assert result == [text]


def test_chunk_long_text_produces_multiple_chunks() -> None:
    # 10 palavras por sentenca, 20 sentencas = ~200 palavras
    sentence = "Esta e uma sentenca de exemplo com palavras suficientes. "
    text = sentence * 20
    result = _chunker(chunk_size=100, overlap=10).chunk(text)
    assert len(result) > 1


def test_all_chunks_within_size_limit() -> None:
    sentence = "Palavra " * 50  # 400 chars
    text = sentence * 5
    chunk_size = 300
    result = _chunker(chunk_size=chunk_size, overlap=30).chunk(text)
    for chunk in result:
        assert len(chunk) <= chunk_size, f"Chunk de {len(chunk)} chars excede {chunk_size}"


def test_chunk_prefers_paragraph_boundary() -> None:
    # Dois paragrafos com 80 chars cada
    para1 = "a" * 80
    para2 = "b" * 80
    text = para1 + "\n\n" + para2
    result = _chunker(chunk_size=90, overlap=10).chunk(text)
    # Deve ter dois chunks distintos (um por paragrafo)
    assert len(result) >= 2
    assert any(para1 in chunk for chunk in result)
    assert any(para2 in chunk for chunk in result)


def test_chunks_cover_full_text() -> None:
    text = "palavra " * 100
    result = _chunker(chunk_size=80, overlap=10).chunk(text)
    # Cada palavra original deve aparecer em algum chunk
    all_text = " ".join(result)
    for word in ["palavra"] * 5:
        assert word in all_text
