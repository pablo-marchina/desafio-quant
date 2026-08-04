import asyncio
from datetime import datetime, timezone

from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
from graphiti_core.llm_client.groq_client import GroqClient
from graphiti_core.llm_client.config import LLMConfig, ModelSize
from graphiti_core.driver.neo4j_driver import Neo4jDriver
from graphiti_core.prompts.models import Message
from pydantic import BaseModel
import typing

from config.settings import settings
from scraping.generic import scrape_url
from rag.embbedings import LocalEmbedder
from rag.reranker import LocalReranker


# llama-4-scout tem max_tokens <= 8192 mas edge_operations.py hardcoda 16384
# subclass cappa o valor antes de chegar no Groq
class CappedGroqClient(GroqClient):
    async def _generate_response(
        self,
        messages: list[Message],
        response_model: type[BaseModel] | None = None,
        max_tokens: int = 2048,
        model_size: ModelSize = ModelSize.medium,
    ) -> dict[str, typing.Any]:
        return await super()._generate_response(
            messages, response_model, min(max_tokens, 8000), model_size
        )


# 16 tecnologias NVIDIA do TAPI (seção 5.4 e 8.2)
# Cada uma vira um episódio no grafo: nome + caso de uso + texto scrapado da doc oficial
NVIDIA_TECHS = {
    "NVIDIA Inception": {
        "url": "https://www.nvidia.com/en-us/startups/",
        "use_case": "Programa para startups: benefícios, comunidade, credits, suporte técnico e go-to-market.",
    },
    "NVIDIA NIM": {
        "url": "https://www.nvidia.com/en-us/ai-data-science/products/nim-microservices/",
        "use_case": "Microservices para deploy de modelos de IA otimizados.",
    },
    "NVIDIA NeMo": {
        "url": "https://www.nvidia.com/en-us/ai-data-science/products/nemo/",
        "use_case": "Treinamento, customização, avaliação e guardrails para modelos generativos.",
    },
    "NeMo Guardrails": {
        "url": "https://github.com/NVIDIA/NeMo-Guardrails",
        "use_case": "Controle de comportamento de assistentes e agentes.",
    },
    "NVIDIA Triton Inference Server": {
        "url": "https://developer.nvidia.com/triton-inference-server",
        "use_case": "Serving de modelos em produção.",
    },
    "TensorRT-LLM": {
        "url": "https://github.com/NVIDIA/TensorRT-LLM",
        "use_case": "Otimização de inferência de LLMs.",
    },
    "NVIDIA RAPIDS": {
        "url": "https://rapids.ai/",
        "use_case": "Aceleração de pipelines de dados com GPU.",
    },
    "cuDF": {
        "url": "https://docs.rapids.ai/api/cudf/stable/",
        "use_case": "Processamento de dataframes em GPU.",
    },
    "cuML": {
        "url": "https://docs.rapids.ai/api/cuml/stable/",
        "use_case": "Machine learning acelerado em GPU.",
    },
    "CUDA": {
        "url": "https://developer.nvidia.com/cuda-toolkit",
        "use_case": "Programação paralela em GPU.",
    },
    "NVIDIA Riva": {
        "url": "https://developer.nvidia.com/riva",
        "use_case": "ASR, TTS e modelos de voz.",
    },
    "NVIDIA Omniverse": {
        "url": "https://www.nvidia.com/en-us/omniverse/",
        "use_case": "Simulação, 3D e digital twins.",
    },
    "NVIDIA Isaac": {
        "url": "https://developer.nvidia.com/isaac",
        "use_case": "Robotics, simulação e autonomia.",
    },
    "NVIDIA Clara": {
        "url": "https://www.nvidia.com/en-us/clara/",
        "use_case": "Healthcare e life sciences.",
    },
    "NVIDIA Morpheus": {
        "url": "https://developer.nvidia.com/morpheus-cybersecurity",
        "use_case": "Cybersecurity com IA acelerada.",
    },
    "NVIDIA AI Enterprise": {
        "url": "https://www.nvidia.com/en-us/data-center/products/ai-enterprise/",
        "use_case": "Plataforma empresarial para IA em produção.",
    },
}


async def ingest_nvidia_techs():
    """
    Ingere as 16 tecnologias NVIDIA no grafo Neo4j via Graphiti.
    Cada tech vira um episódio: o LLM extrai entidades e relações,
    o embedder gera os vetores, tudo é salvo no Neo4j.
    """
    llm = CappedGroqClient(LLMConfig(
        api_key=settings.groq_api_key,
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        max_tokens=2048,
    ))
    driver = Neo4jDriver(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
        database=settings.neo4j_database,
    )
    graphiti = Graphiti(
        graph_driver=driver,
        llm_client=llm,
        embedder=LocalEmbedder(),
        cross_encoder=LocalReranker(),
    )

    # cria índices e constraints no Neo4j (idempotente — pode rodar várias vezes)
    await graphiti.build_indices_and_constraints()

    for name, info in NVIDIA_TECHS.items():
        print(f"[ingestion] scraping {name}...")
        scraped = scrape_url(info["url"])

        if not scraped:
            print(f"[ingestion] ✗ falha ao scrapar {name}, pulando")
            continue

        # trunca texto agressivamente: Graphiti adiciona prompt próprio + episódios anteriores como contexto
        # ~1500 chars ≈ 375 tokens, deixa ~10000 tokens livres pro overhead interno do Graphiti
        texto = scraped["text"][:1500]

        # monta o corpo do episódio: caso de uso + texto da doc oficial
        episode_body = f"Tecnologia NVIDIA: {name}\nCaso de uso: {info['use_case']}\n\n{texto}"

        # group_id isolado por tech: Graphiti não puxa episódios anteriores como contexto
        # sem isso, cada nova ingestão acumula tokens de todas as anteriores → estoura 12k TPM
        group_id = name.lower().replace(" ", "_").replace("/", "_")
        try:
            await graphiti.add_episode(
                name=name,
                episode_body=episode_body,
                source_description=f"Documentação oficial NVIDIA — {name}",
                reference_time=datetime.now(timezone.utc),
                source=EpisodeType.text,
                group_id=group_id,
            )
            print(f"[ingestion] ✓ {name} ingerido no grafo")
        except Exception as e:
            print(f"[ingestion] ✗ {name} falhou: {e}")

        # pausa pra respeitar limite de tokens/min do Groq free tier
        await asyncio.sleep(20)

    await graphiti.close()
    print("\n[ingestion] base NVIDIA ingerida com sucesso")


if __name__ == "__main__":
    asyncio.run(ingest_nvidia_techs())
