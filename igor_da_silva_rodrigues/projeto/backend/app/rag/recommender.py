from __future__ import annotations

from typing import Any

from app.core.contracts import validate_contract
from app.core.observability import logged_stage
from app.core.schemas import AIMaturityOutput, NVIDIARecommendationOutput
from app.rag.config import RAGConfig
from app.rag.generator import RecommendationGenerator, create_generator
from app.rag.reranker import BGEReranker, LexicalReranker, Reranker
from app.rag.vector_store import QdrantKnowledgeStore


class NVIDIARecommenderRAG:
    def __init__(
        self,
        store: QdrantKnowledgeStore | Any | None = None,
        reranker: Reranker | None = None,
        generator: RecommendationGenerator | None = None,
        config: RAGConfig | None = None,
    ) -> None:
        self.config = config or RAGConfig.from_env()
        self.store = store or QdrantKnowledgeStore(config=self.config)
        self.reranker = reranker or _create_reranker(self.config)
        self.generator = generator or create_generator(self.config)

    def recommend(self, maturity: AIMaturityOutput | dict[str, Any]) -> NVIDIARecommendationOutput:
        profile = validate_contract(AIMaturityOutput, maturity)
        if profile.classificacao == "Non-AI":
            return NVIDIARecommendationOutput(
                startup=profile.startup,
                recomendacoes=[],
                chunks_utilizados=[],
                aviso="Startup sem evidência qualificada de IA; RAG não executado.",
            )

        query = _build_query(profile)
        with logged_stage("nvidia_recommender_rag", startup=profile.startup) as metrics:
            retrieved = self.store.hybrid_search(
                query,
                top_k=self.config.top_k,
                profile=profile.classificacao,
            )
            reranked = self.reranker.rerank(query, retrieved, top_n=self.config.top_n)
            result = self.generator.generate(profile, reranked)
            if not result.recomendacoes and len(retrieved) > len(reranked):
                expanded_top_n = min(len(retrieved), 20)
                reranked = self.reranker.rerank(query, retrieved, top_n=expanded_top_n)
                result = self.generator.generate(profile, reranked)
            filtered = [
                recommendation
                for recommendation in result.recomendacoes
                if recommendation.tecnologia != "Inception"
            ]
            if len(filtered) != len(result.recomendacoes):
                warning = "NVIDIA Inception e um programa, nao uma tecnologia; item movido para Inception Fit."
                result = result.model_copy(
                    update={
                        "recomendacoes": filtered,
                        "aviso": " ".join(part for part in [result.aviso, warning] if part),
                    }
                )
            metrics["retrieved_count"] = len(retrieved)
            metrics["reranked_count"] = len(reranked)
            metrics["result_count"] = len(result.recomendacoes)
        return validate_contract(NVIDIARecommendationOutput, result)


def _create_reranker(config: RAGConfig) -> Reranker:
    if config.reranker_provider == "bge":
        return BGEReranker(config.reranker_model)
    return LexicalReranker()


def _build_query(profile: AIMaturityOutput) -> str:
    technologies = profile.tecnologias_utilizadas
    detected = (
        technologies.frameworks
        + technologies.modelos_apis
        + technologies.infraestrutura
        + technologies.ferramentas_mlops
    )
    needs = " ".join(profile.necessidades_limitacoes)
    normalized_needs = needs.lower()
    english_expansion = []
    translations = {
        "custo": "NVIDIA NIM Triton TensorRT-LLM cost efficiency inference optimization",
        "latência": "NVIDIA Triton TensorRT-LLM CUDA low latency real-time inference",
        "latencia": "NVIDIA Triton TensorRT-LLM CUDA low latency real-time inference",
        "escala": "NVIDIA Triton NIM scalability throughput deployment",
        "governança": "NVIDIA NeMo AI Enterprise governance compliance audit",
        "governanca": "NVIDIA NeMo AI Enterprise governance compliance audit",
        "privacidade": "NVIDIA NeMo AI Enterprise privacy sensitive data protection",
        "vendor lock-in": "NVIDIA NIM portability self-hosted on-premises",
    }
    for signal, expansion in translations.items():
        if signal in normalized_needs:
            english_expansion.append(expansion)
    return " ".join(
        part
        for part in [
            profile.classificacao,
            f"maturidade {profile.nivel_maturidade}",
            " ".join(detected),
            needs,
            " ".join(english_expansion),
        ]
        if part
    )
