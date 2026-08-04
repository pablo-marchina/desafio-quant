"""Testes da ingestão da base de conhecimento NVIDIA (F3.1).

Garantem que o manifesto do §10 (`data/knowledge_base/sources.yaml`) carrega num modelo
válido, que cada fonte tem conteúdo curado citável, que a ingestão carimba proveniência
(content_sha256 + url) e que o núcleo de techs do §5.4 (§10.2) + MONAI (F3.1c) estão cobertos.
Os materiais AI-native do §10.1 (F3.1d) entram como `grounding` e têm teste dedicado.
"""

from __future__ import annotations

from packages.rag import KBDocument, KBSource, covered_techs, ingest, load_kb_sources
from packages.scraping.provenance import content_hash

# Núcleo de techs do §5.4 que o §10.2 deve trazer para a KB (MONAI -> F3.1c).
CORE_TECHS = {
    "NVIDIA Inception",
    "NVIDIA NIM",
    "NVIDIA API Catalog",
    "NVIDIA NeMo",
    "NeMo Guardrails",
    "NVIDIA Triton Inference Server",
    "TensorRT-LLM",
    "NVIDIA RAPIDS",
    "cuDF",
    "cuML",
    "CUDA Toolkit",
    "NVIDIA Riva",
    "NVIDIA Omniverse",
    "NVIDIA Isaac",
    "NVIDIA Clara",
    "NVIDIA Morpheus",
    "NVIDIA AI Enterprise",
}


def test_manifest_loads_with_unique_ids() -> None:
    sources = load_kb_sources()
    assert len(sources) >= len(CORE_TECHS)
    assert all(isinstance(s, KBSource) for s in sources)
    ids = [s.id for s in sources]
    assert len(ids) == len(set(ids))  # IDs únicos (o loader também valida)


def test_every_source_is_well_formed() -> None:
    for s in load_kb_sources():
        assert s.url.startswith("http")
        assert s.section in {"10.1", "10.2"}
        assert s.source_type in {"doc", "blog", "video_transcript", "grounding"}
        assert s.access  # nota de acesso/licença sempre declarada
        assert s.content_path.is_file()  # conteúdo curado existe


def test_ingest_produces_documents_with_provenance() -> None:
    docs = ingest()
    assert len(docs) == len(load_kb_sources())
    for d in docs:
        assert isinstance(d, KBDocument)
        assert d.text.strip()  # nada vazio entra na KB
        assert d.url.startswith("http")  # toda afirmação tem fonte rastreável (§8)
        assert d.content_sha256 == content_hash(d.text)
        assert d.char_count == len(d.text)


def test_section_10_2_core_techs_are_covered() -> None:
    # Cobertura do §10.2: todas as techs do §5.4 ingeridas e recuperáveis (base p/ F3.8).
    assert CORE_TECHS <= covered_techs()


def test_monai_is_covered_for_healthcare() -> None:
    # F3.1c: MONAI é citado no §5.5 como alvo em saúde, mas não tem entrada no §10. Precisa
    # estar na KB (como `doc` na seção 10.2) para ser recuperável pelo RAG.
    monai = next((s for s in load_kb_sources() if s.id == "monai"), None)
    assert monai is not None
    assert monai.tech == "MONAI"
    assert monai.source_type == "doc"
    assert "MONAI" in covered_techs()


def test_grounding_materials_ground_the_aimi_rubric() -> None:
    # F3.1d: os materiais AI-native do §10.1 (Sequoia/Emergence/NVIDIA 5-layer cake) são a
    # origem conceitual dos pilares do AIMI. Entram como `grounding` na seção 10.1 (não como
    # tech recomendável) e precisam estar na KB para sustentar a rubrica de forma rastreável.
    grounding_ids = {
        "sequoia-services-as-software",
        "emergence-ai-native-services-playbook",
        "nvidia-ai-5-layer-cake",
    }
    by_id = {s.id: s for s in load_kb_sources()}
    assert grounding_ids <= by_id.keys()
    for gid in grounding_ids:
        src = by_id[gid]
        assert src.source_type == "grounding"
        assert src.section == "10.1"  # materiais do §10.1, não docs do §10.2
        assert src.tech not in CORE_TECHS  # grounding não polui as techs recomendáveis (§5.4)
    # São ingeríveis com proveniência como qualquer outra fonte (mesmo loader, sem reabrir).
    docs = {d.id: d for d in ingest()}
    assert all(docs[gid].text.strip() and docs[gid].url.startswith("http") for gid in grounding_ids)


def test_ingest_is_deterministic_offline() -> None:
    # Mesmo conteúdo -> mesmo hash entre runs (reprodutibilidade, sem rede).
    first = {d.id: d.content_sha256 for d in ingest()}
    second = {d.id: d.content_sha256 for d in ingest()}
    assert first == second


def test_ingest_accepts_a_source_subset() -> None:
    sources = load_kb_sources()
    subset = ingest(sources[:3])
    assert {d.id for d in subset} == {s.id for s in sources[:3]}
