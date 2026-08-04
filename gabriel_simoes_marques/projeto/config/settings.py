# config/settings.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    groq_api_key: str
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    neo4j_database: str = "neo4j"
    openrouter_api_key: str = ""
    llm_model: str = "llama-3.3-70b-versatile"
    embedding_model: str = "intfloat/multilingual-e5-large"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"

    class Config:
        env_file = ".env"

settings = Settings()


