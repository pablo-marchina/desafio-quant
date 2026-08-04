from types import SimpleNamespace

from app.core.schemas import KnowledgeSourceInput, LoadedKnowledgeDocument
from app.rag.chunking import NVIDIAChunker
from app.rag.document_loader import clean_document_text
from app.rag.ingestion import NVIDIAKnowledgeIngestor


SOURCE = KnowledgeSourceInput(
    titulo="Triton Docs",
    url="https://docs.nvidia.com/triton",
    tecnologia="Triton",
    tipo="documentacao",
    dores_relacionadas=["latencia", "escalabilidade"],
    perfil_aplicavel=["AI-native", "AI-enabled"],
)


def test_document_cleaner_removes_repeated_navigation_noise():
    text = "\n".join(["Menu global"] * 5 + ["# Triton", "Conteudo tecnico", "Conteudo tecnico"])

    cleaned = clean_document_text(text)

    assert "Menu global" not in cleaned
    assert cleaned.count("Conteudo tecnico") == 1


def test_chunker_generates_stable_ids_and_required_metadata():
    document = LoadedKnowledgeDocument(
        titulo="Triton Docs",
        content="# Deploy\n" + "Triton reduz latencia de inferencia. " * 80,
        source=SOURCE,
    )
    chunker = NVIDIAChunker(chunk_size=800, chunk_overlap=100)

    first = chunker.split(document)
    second = chunker.split(document)

    assert len(first) > 1
    assert [item.chunk_id for item in first] == [item.chunk_id for item in second]
    assert first[0].metadata.tecnologia == "Triton"
    assert first[0].metadata.url_fonte == SOURCE.url


class FakeLoader:
    def load(self, source):
        if "falha" in source.url:
            raise ValueError("fonte indisponivel")
        return LoadedKnowledgeDocument(
            titulo=source.titulo,
            content="# Secao\n" + "Conteudo tecnico NVIDIA para inferencia. " * 10,
            source=source,
        )


class FakeStore:
    def __init__(self):
        self.config = SimpleNamespace(collection_name="nvidia_knowledge")
        self.chunks = []

    def upsert_chunks(self, chunks, batch_size=100):
        self.chunks.extend(chunks)
        return len(chunks)


def test_ingestion_continues_when_one_source_fails():
    failing = SOURCE.model_copy(update={"url": "https://docs.nvidia.com/falha"})
    store = FakeStore()
    ingestor = NVIDIAKnowledgeIngestor(
        loader=FakeLoader(),
        store=store,
        retry_wait_multiplier=0,
    )

    report = ingestor.run([SOURCE, failing])

    assert report.status == "parcial"
    assert report.fontes_processadas == 1
    assert report.fontes_com_erro == 1
    assert report.chunks_inseridos == len(store.chunks)
