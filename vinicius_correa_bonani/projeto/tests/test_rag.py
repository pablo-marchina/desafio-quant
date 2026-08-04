"""Testes de chunking e limpeza de corpus (funções puras, sem Qdrant/embeddings)."""

from app.rag import chunk_texto, limpar


def test_limpar_remove_changelog_e_emoji():
    texto = "\n".join([
        "Triton serve modelos de IA em produção com eficiência.",
        "[2024/11/09] 🚀🚀🚀 3x Faster AllReduce",
        "🔥🔥🔥 ⭐ ➡️",
        "TensorRT-LLM otimiza a inferência de LLMs.",
    ])
    out = limpar(texto)
    assert "Triton serve modelos" in out
    assert "TensorRT-LLM" in out
    assert "2024/11/09" not in out      # linha de changelog removida
    assert "🚀" not in out              # linha de emoji removida


def test_chunk_divide_e_preserva_fonte_titulo():
    texto = "\n".join(f"Paragrafo {i} com algum conteudo de teste aqui." for i in range(40))
    chunks = chunk_texto(texto, fonte="https://x.com", titulo="X", tamanho=200, overlap=40)

    assert len(chunks) > 1
    assert all(c["fonte"] == "https://x.com" for c in chunks)
    assert all(c["titulo"] == "X" for c in chunks)
    assert all(c["texto"].strip() for c in chunks)


def test_chunk_texto_curto_vira_um_chunk():
    chunks = chunk_texto("texto curto", fonte="f")
    assert len(chunks) == 1
    assert chunks[0]["texto"] == "texto curto"
