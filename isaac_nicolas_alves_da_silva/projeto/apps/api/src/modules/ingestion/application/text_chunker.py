"""Servico de divisao de texto em chunks para embedding."""

from langchain_text_splitters import RecursiveCharacterTextSplitter


class TextChunker:
    """Divide texto limpo em fragmentos de tamanho controlado com sobreposicao.

    Usa RecursiveCharacterTextSplitter do LangChain, que respeita a estrutura
    do texto: paragrafo (\n\n) > linha (\n) > sentenca (". ") > palavra > char.
    Chunks menores que _MIN_CHUNK_CHARS sao descartados para evitar ruido no
    embedding.
    """

    _MIN_CHUNK_CHARS = 50

    def __init__(
        self,
        chunk_size: int = 2000,
        chunk_overlap: int = 200,
    ) -> None:
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    def chunk(self, text: str) -> list[str]:
        if not text:
            return []
        chunks = self._splitter.split_text(text)
        # Quando nao ha split (texto cabe num unico chunk), retorna direto.
        # O filtro de tamanho minimo so se aplica a fragmentos gerados pelo split,
        # nao ao texto completo.
        if len(chunks) <= 1:
            return chunks
        return [c for c in chunks if len(c.strip()) >= self._MIN_CHUNK_CHARS]
