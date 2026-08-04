"""Chunking: quebra um texto longo em pedaços (chunks) antes de vetorizar.

Versão mínima: janela deslizante por caracteres, com sobreposição.
Chunking "semântico" (quebrar em fronteiras de frase/seção) é enriquecimento.
"""

from __future__ import annotations

CHUNK_SIZE = 800       # tamanho-alvo de cada chunk, em caracteres
CHUNK_OVERLAP = 100    # sobreposição entre chunks vizinhos (mantém contexto)

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Quebra o texto em pedaços de ~chunk_size caracteres, com sobreposição.

    A sobreposição faz pedaços vizinhos compartilharem um trecho, pra não
    perder o contexto que cai bem na "emenda" entre dois chunks.
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end].strip())
        start = end - overlap  # recua um pouco => gera a sobreposição
    return chunks
