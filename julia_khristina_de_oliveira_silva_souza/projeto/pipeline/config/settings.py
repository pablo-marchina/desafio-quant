import os
from dotenv import load_dotenv

load_dotenv()

# RAG
TOP_K_RAG = 15
RERANK_TOP_N = 5

# Validação
MIN_EVIDENCE_SCORE = float(os.getenv("MIN_EVIDENCE_SCORE", "0.0"))

# Pipeline
MAX_STARTUPS_PER_RUN = int(os.getenv("MAX_STARTUPS_PER_RUN", "100"))
SCRAPING_DELAY_SECONDS = 2
MAX_RECOMENDACOES_POR_STARTUP = 3

# Modelos Cohere
COHERE_EMBED_MODEL = "embed-multilingual-v3.0"
COHERE_RERANK_MODEL = "rerank-multilingual-v3.0"
COHERE_CHAT_MODEL = "command-r-08-2024"

# Pesos do Score de Fit NVIDIA (classifier)
PESO_AI_CLASS = 0.4
PESO_SETOR = 0.25
PESO_EVIDENCIA = 0.2
PESO_MOMENTUM = 0.15

# Banco
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/nvidia_radar")

# Caminhos
QDRANT_PATH = os.getenv("QDRANT_PATH", "./src/qdrant_local")
CHUNKS_PATH = os.getenv("CHUNKS_PATH", "./src/chunks_with_embeddings.json")
