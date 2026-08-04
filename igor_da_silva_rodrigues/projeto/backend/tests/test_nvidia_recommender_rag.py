from app.core.schemas import (
    AIMaturityOutput,
    KnowledgeMetadata,
    RetrievedChunk,
)
from app.rag.config import RAGConfig
from app.rag.recommender import NVIDIARecommenderRAG


def _profile(classification="AI-native"):
    return AIMaturityOutput(
        startup="Startup Teste",
        classificacao=classification,
        nivel_maturidade=4 if classification != "Non-AI" else 0,
        confianca_classificacao=0.9,
        justificativa="Evidencias qualificadas.",
        tecnologias_utilizadas={
            "frameworks": ["PyTorch"],
            "modelos_apis": [],
            "infraestrutura": ["GPU"],
            "ferramentas_mlops": [],
        },
        necessidades_limitacoes=["Possível necessidade de reduzir latência de inferência"],
        evidencias_suporte=["https://startup.example: usa PyTorch"],
    )


def _retrieved(chunk_id, technology, score):
    return RetrievedChunk(
        chunk_id=chunk_id,
        content=f"{technology} ajuda a otimizar inferencia e reduzir latencia.",
        metadata=KnowledgeMetadata(
            tecnologia=technology,
            tipo="documentacao",
            dores_relacionadas=["latencia"],
            perfil_aplicavel=["AI-native", "AI-enabled"],
            titulo_secao="Inference",
            url_fonte=f"https://docs.nvidia.com/{technology.lower()}",
        ),
        retrieval_score=score,
    )


class FakeStore:
    def __init__(self):
        self.calls = []

    def hybrid_search(self, query, top_k, profile):
        self.calls.append((query, top_k, profile))
        return [
            RetrievedChunk(
                chunk_id="irrelevante",
                content="Belgique, Brasil, Canada, Czech Republic, Denmark.",
                metadata=KnowledgeMetadata(
                    tecnologia="Inception",
                    tipo="documentacao",
                    dores_relacionadas=["latencia"],
                    perfil_aplicavel=["AI-native"],
                    titulo_secao="Countries",
                    url_fonte="https://www.nvidia.com/en-us/startups/",
                ),
                retrieval_score=1.0,
            ),
            _retrieved("triton-1", "Triton", 0.9),
            _retrieved("tensorrt-1", "TensorRT-LLM", 0.8),
            _retrieved("nemo-1", "NeMo", 0.5),
        ]


def test_recommender_returns_only_grounded_official_technologies():
    store = FakeStore()
    rag = NVIDIARecommenderRAG(
        store=store,
        config=RAGConfig(top_k=20, top_n=2),
    )

    result = rag.recommend(_profile())

    assert len(result.chunks_utilizados) == 2
    assert {item.tecnologia for item in result.recomendacoes} <= {"Triton", "TensorRT-LLM"}
    assert "Inception" not in {item.tecnologia for item in result.recomendacoes}
    assert all(item.citacoes for item in result.recomendacoes)
    assert all("https://docs.nvidia.com" in citation for item in result.recomendacoes for citation in item.citacoes)
    assert store.calls[0][1:] == (20, "AI-native")


def test_recommender_skips_retrieval_for_non_ai_startup():
    store = FakeStore()
    rag = NVIDIARecommenderRAG(store=store, config=RAGConfig())

    result = rag.recommend(_profile("Non-AI"))

    assert result.recomendacoes == []
    assert result.aviso
    assert store.calls == []


def test_recommender_accepts_technology_identified_by_official_metadata():
    class MetadataStore:
        def hybrid_search(self, query, top_k, profile):
            return [
                RetrievedChunk(
                    chunk_id="triton-metadata",
                    content="Deploy models with dynamic batching and concurrent execution.",
                    metadata=KnowledgeMetadata(
                        tecnologia="Triton",
                        tipo="documentacao",
                        dores_relacionadas=["latencia"],
                        perfil_aplicavel=["AI-native", "AI-enabled"],
                        titulo_secao="NVIDIA Triton Inference Server Documentation",
                        url_fonte="https://docs.nvidia.com/deeplearning/triton-inference-server/",
                    ),
                    retrieval_score=0.9,
                )
            ]

    rag = NVIDIARecommenderRAG(
        store=MetadataStore(),
        config=RAGConfig(top_k=10, top_n=3),
    )
    profile = _profile().model_copy(
        update={"necessidades_limitacoes": ["Equipe especializada ainda nao comprovada"]}
    )

    result = rag.recommend(profile)

    assert [item.tecnologia for item in result.recomendacoes] == ["Triton"]
    assert "triton-metadata" in result.recomendacoes[0].citacoes[0]


def test_recommender_expands_reranking_when_initial_window_has_no_support():
    irrelevant = [
        RetrievedChunk(
            chunk_id=f"irrelevant-{index}",
            content="General program information and available countries.",
            metadata=KnowledgeMetadata(
                tecnologia="Inception",
                tipo="documentacao",
                dores_relacionadas=["latencia"],
                perfil_aplicavel=["AI-native"],
                titulo_secao="Countries",
                url_fonte="https://www.nvidia.com/en-us/startups/",
            ),
            retrieval_score=1.0 - index * 0.01,
        )
        for index in range(5)
    ]
    supported = _retrieved("triton-late", "Triton", 0.7)

    class ExpandingStore:
        def hybrid_search(self, query, top_k, profile):
            return [*irrelevant, supported]

    class StableReranker:
        def rerank(self, query, chunks, top_n):
            return chunks[:top_n]

    rag = NVIDIARecommenderRAG(
        store=ExpandingStore(),
        reranker=StableReranker(),
        config=RAGConfig(top_k=20, top_n=5),
    )

    result = rag.recommend(_profile())

    assert [item.tecnologia for item in result.recomendacoes] == ["Triton"]
    assert [chunk.chunk_id for chunk in result.chunks_utilizados] == ["triton-late"]
