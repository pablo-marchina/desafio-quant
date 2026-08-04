"""Configuração central do projeto, lida do .env uma única vez.

Use `from app.config import settings` em qualquer lugar — nunca leia variáveis
de ambiente espalhadas pelo código. Isso mantém a troca SQLite→Postgres e
Qdrant-local→servidor num só lugar.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Chaves de API
    openai_api_key: str = ""
    groq_api_key: str = ""
    nvidia_api_key: str = ""
    huggingface_api_key: str = ""
    gemini_api_key: str = ""
    cohere_api_key: str = ""

    # Banco relacional (SQLite embarcado por enquanto)
    database_url: str = "sqlite:///radar.db"

    # Banco vetorial (Qdrant). `qdrant_url` ligado (ex.: http://localhost:6333)
    # usa o servidor Docker; vazio cai para o modo local embarcado (`qdrant_path`).
    qdrant_url: str = ""
    qdrant_path: str = "./qdrant"

    # LLM (extração estruturada no Extractor). Servido pela Groq (API compatível
    # com OpenAI) quando há GROQ_API_KEY; senão, OpenAI direto.
    llm_model: str = "openai/gpt-oss-20b"
    # Retries do cliente LLM: o tier grátis da Groq tem 8000 TPM e as melhorias
    # (self-consistency, painel, reflection) disparam ~10 chamadas em rajada. O 429 é
    # transitório ("try again in Xs") e o cliente honra o backoff — só precisa de fôlego.
    llm_max_retries: int = 6
    # Timeout do ChatNVIDIA: o tier grátis "build" da NVIDIA tem latência alta
    # (cold start/fila ~30-100s por chamada). O default de 60s estoura → subimos.
    nvidia_timeout: int = 180

    # Coleta web
    user_agent: str = "NVIDIA-Startup-Radar/0.1 (+pesquisa academica Inteli)"
    http_timeout: float = 15.0
    busca_top_n: int = 12   # mais fontes/rodada → evidência mais saturada e estável

    # Classifier: self-consistency (classifica N vezes e vota a maioria) + temperatura
    # (>0 para os votos variarem; a maioria compensa o ruído). N=1 desliga a votação.
    classifier_n_votos: int = 3
    classifier_temperatura: float = 0.4

    # Score: painel de juízes (pontua N vezes e faz a média das notas) + temperatura.
    # N=1 desliga o painel. Análogo numérico da self-consistency do Classifier.
    score_n_juizes: int = 3
    score_temperatura: float = 0.4

    # Briefing: passada de reflection (revisa o rascunho contra as fontes, removendo
    # número sem lastro e citação incoerente). False (ou sem chave LLM) pula a revisão.
    briefing_reflection: bool = True

    # Loop do Evidence Validator (teto de tentativas de coleta)
    max_tentativas: int = 2
    # Grounding (faithfulness check) do Evidence Validator. False (ou sem chave LLM)
    # cai para a regra mecânica antiga — mantém offline/testes robustos.
    grounding_habilitado: bool = True

    # RAG: embeddings, Qdrant e rerank
    # "gemini" (multilíngue, grátis) | "openai" | "local" (fastembed, grátis/offline)
    embedding_provider: str = "gemini"
    embedding_model: str = "text-embedding-3-small"        # usado se provider=openai
    gemini_embedding_model: str = "models/gemini-embedding-001"  # usado se provider=gemini
    qdrant_collection: str = "nvidia"
    rag_top_k: int = 50                          # candidatos da busca híbrida (recall)
    rag_top_n: int = 5                           # após o rerank (precisão)
    cohere_rerank_model: str = "rerank-v3.5"

    # Score composto: pesos configuráveis (somam 1.0).
    w_ai_native: float = 0.30
    w_nvidia_fit: float = 0.30
    w_tracao: float = 0.20
    w_time_ia: float = 0.20

    @property
    def llm_provider(self) -> str:
        """Provedor ativo do LLM (precedência: NVIDIA → HuggingFace → Groq → OpenAI).
        Para trocar, comente/apague a chave do provedor que não quer usar no .env."""
        if self.nvidia_api_key:
            return "nvidia"
        if self.huggingface_api_key:
            return "huggingface"
        if self.groq_api_key:
            return "groq"
        return "openai"

    @property
    def llm_base_url(self) -> str | None:
        """URL base do caminho ChatOpenAI (Groq/HF/OpenAI são todos OpenAI-compat).
        O provedor NVIDIA usa o cliente ChatNVIDIA e não passa por aqui."""
        p = self.llm_provider
        if p == "groq":
            return "https://api.groq.com/openai/v1"
        if p == "huggingface":
            return "https://router.huggingface.co/v1"
        return None  # OpenAI usa o default

    @property
    def llm_api_key(self) -> str:
        """Chave do LLM do provedor ativo. Também usada pelos guards (grounding/reflection
        só ligam quando há chave)."""
        return (
            self.nvidia_api_key
            or self.huggingface_api_key
            or self.groq_api_key
            or self.openai_api_key
        )


settings = Settings()
