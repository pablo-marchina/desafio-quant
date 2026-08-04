from graphiti_core import Graphiti
from config.settings import settings
from graphiti_core.llm_client.groq_client import GroqClient
from graphiti_core.embedder import EmbedderClient
from graphiti_core.llm_client.openai_client import OpenAIClient
from graphiti_core.llm_client.config import LLMConfig
import asyncio
from rag.embbedings import LocalEmbedder
from rag.reranker import LocalReranker


async def get_graphiti():

	llm = GroqClient(LLMConfig(
		api_key=settings.groq_api_key,
		model=settings.llm_model,
	))

	embedder = LocalEmbedder()
	cross_encoder = LocalReranker()

	client = Graphiti(
		uri=settings.neo4j_uri,
		user=settings.neo4j_user,
		password=settings.neo4j_password,
		llm_client=llm,
		embedder=embedder,
		cross_encoder=cross_encoder
	)

	return client

if __name__ == "__main__":
	client = asyncio.run(get_graphiti())
	print("Graphiti Conection Estabilish")