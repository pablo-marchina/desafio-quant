"""Testes do chunking — offline e determinísticos (tiktoken roda local)."""
import pytest

from rag.chunk import chunk_corpus, chunk_doc, chunk_text
from rag.ingest import NvidiaDoc


def test_texto_curto_vira_um_chunk_so():
    assert chunk_text("um texto bem curto", max_tokens=300) == ["um texto bem curto"]


def test_texto_vazio_nao_gera_chunk():
    assert chunk_text("   ", max_tokens=300) == []


def test_texto_longo_quebra_em_varias_janelas():
    texto = " ".join(f"palavra{i}" for i in range(500))
    chunks = chunk_text(texto, max_tokens=50, overlap=10)
    assert len(chunks) > 1
    assert all(c.strip() for c in chunks)


def test_janelas_se_sobrepoem():
    # com overlap, o fim de um chunk reaparece no começo do próximo
    texto = " ".join(f"t{i}" for i in range(200))
    chunks = chunk_text(texto, max_tokens=40, overlap=10)
    fim_do_primeiro = chunks[0].split()[-1]
    assert fim_do_primeiro in chunks[1]


def test_overlap_maior_que_max_tokens_eh_erro():
    with pytest.raises(ValueError):
        chunk_text("qualquer", max_tokens=10, overlap=10)


def test_chunk_doc_preserva_proveniencia_e_indice():
    texto = " ".join(f"w{i}" for i in range(300))
    doc = NvidiaDoc(tech="NVIDIA NIM", url="https://x/nim", text=texto)
    chunks = chunk_doc(doc, max_tokens=50, overlap=10)

    assert all(c.tech == "NVIDIA NIM" and c.url == "https://x/nim" for c in chunks)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_chunk_corpus_achata_varios_docs():
    docs = [
        NvidiaDoc(tech="A", url="https://a", text=" ".join(f"a{i}" for i in range(200))),
        NvidiaDoc(tech="B", url="https://b", text="curto"),
    ]
    chunks = chunk_corpus(docs, max_tokens=40, overlap=10)
    techs = {c.tech for c in chunks}
    assert techs == {"A", "B"}
