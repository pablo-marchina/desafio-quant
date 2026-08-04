"""Configuração central do TAPI (F0.3).

Carrega o ambiente (`.env` / variáveis de processo) de forma tipada com
`pydantic-settings`. É a fonte única de config consumida por todas as camadas:
migrações/DB (F0.6), cliente Nemotron (F0.7), Langfuse (F0.8), RAG (F3), API/worker
(F5/F2). Os nomes espelham `.env.example` (case-insensitive).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

RerankerProvider = Literal["nemo", "cohere"]
CacheBackend = Literal["disk", "redis"]


class Settings(BaseSettings):
    """Configuração da aplicação, validada a partir do ambiente."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- LLM / NVIDIA -----------------------------------------------------------
    nvidia_api_key: str = Field(default="", description="Chave build.nvidia.com (Nemotron/NIM).")
    nemotron_model_fast: str = "nvidia/llama-3.1-nemotron-nano-8b-v1"
    nemotron_model_reason: str = "nvidia/llama-3.3-nemotron-super-49b-v1"
    # NeMo Retriever (catálogo build.nvidia.com). Os llama-3.2-nv-*qa-1b-v2 atingiram EOL em
    # 2026-05-18 (HTTP 410); os sucessores são a família llama-nemotron-*-1b-v2 (embed mantém
    # dim=2048, compatível com NV_EMBEDQA_DIM/índice F3.4).
    nv_embed_model: str = "nvidia/llama-nemotron-embed-1b-v2"
    nv_rerank_model: str = "nvidia/llama-nemotron-rerank-1b-v2"

    # NIM self-hosted (GPU local) — opcional no build, usado no F6.
    nim_base_url: str = "http://localhost:8000/v1"

    # GPU Graduation Engine (F6.9–F6.11): por padrão off (espinha verde — gpu_benchmark é no-op,
    # recs sem ROI). Ligue p/ o nó anexar o ROIEstimate da matriz às recs de graduação (NIM/
    # TensorRT-LLM/Triton); a matriz vem de data/benchmark/matrix.json (medir o NIM hospedado
    # ao vivo: scripts/bench_nim.py). `benchmark_tier` escolhe a célula usada no mapeamento (F6.11).
    gpu_benchmark_use_matrix: bool = Field(
        default=False, description="gpu_benchmark (F6) anexa ROI da matriz às recs de graduação."
    )
    benchmark_tier: str = Field(
        default="medium", description="Célula (tier) da matriz de benchmark usada no ROI (F6.11)."
    )

    # search_planner (F2.3): por padrão é determinista/offline (reproduzível, sem rede).
    # Ligue p/ deixar o Nemotron-Nano refinar o plano de coleta (requer nvidia_api_key).
    planner_use_llm: bool = Field(
        default=False, description="search_planner (F2.3) usa o Nano p/ refinar o plano."
    )

    # extractor (F2.5): por padrão offline (no-op limpo — espinha reproduzível sem rede).
    # Ligue p/ o nó estruturar os docs com o Nemotron-Super (requer nvidia_api_key).
    extractor_use_llm: bool = Field(
        default=False, description="extractor (F2.5) usa o Super p/ estruturar o StartupProfile."
    )

    # Reasoning do Super na extração (F2.5): ON por padrão (qualidade, eval F7). Desligar deixa a
    # extração MUITO mais rápida (sem a cadeia de raciocínio longa) — útil quando o NIM está lento/
    # limitado, evitando o read timeout e o teto do job RQ (demo). Custa um pouco de qualidade.
    extractor_reasoning: bool = Field(
        default=True, description="extractor (F2.5) liga o reasoning do Super (lento, +qualidade)."
    )

    # classifier (F2.6): por padrão usa a heurística AIMI v0 determinista/offline (reproduzível).
    # Ligue p/ o nó diagnosticar classe+AIMI com o Nemotron-Super (requer nvidia_api_key).
    classifier_use_llm: bool = Field(
        default=False, description="classifier (F2.6) usa o Super p/ pontuar classe + AIMI."
    )

    # recommender (F4.2): por padrão monta a recomendação pela espinha determinista (regras F4.1
    # + evidência recuperada), offline/reproduzível. Ligue p/ o Nemotron-Super refinar as
    # justificativas/próxima-ação ancorado na evidência (requer nvidia_api_key); cai na espinha
    # a qualquer falha. A evidência dos dois lados nunca vem do LLM (anti-alucinação).
    recommender_use_llm: bool = Field(
        default=False, description="recommender (F4.2) usa o Super p/ refinar as recomendações."
    )

    # briefing (F4.4): por padrão monta o relatório executivo pela espinha determinista (diagnóstico
    # + recomendações, ambos já com evidência), offline/reproduzível. Ligue p/ o Nemotron-Super
    # refinar a redação (resumo + os três eixos) ancorado no esqueleto (requer nvidia_api_key); cai
    # na espinha a qualquer falha. Diagnóstico e recomendações nunca vêm do LLM (anti-alucinação).
    briefing_use_llm: bool = Field(
        default=False, description="briefing (F4.4) usa o Super p/ refinar a redação do relatório."
    )

    # Guardrails do briefing (F4.5): o rail de evidência (nenhuma recomendação sem os dois lados)
    # roda SEMPRE; por padrão é a checagem determinista/offline (espinha verde — bloqueia sem rede,
    # reproduzível). Ligue p/ orquestrar o mesmo rail via NeMo Guardrails (Colang + custom action)
    # no container Linux/GPU (dep nemoguardrails; adiada no Windows por puxar annoy/C++). O veredito
    # é sempre determinista — o LLM nunca decide se há evidência (anti-alucinação); cai na espinha a
    # qualquer falha de dep/config.
    briefing_use_guardrails: bool = Field(
        default=False, description="briefing (F4.5) orquestra o rail de evidência via NeMo."
    )

    # Embeddings da KB (F3.3): por padrão usa o HashingEmbedder offline/determinista (espinha
    # verde — reproduzível, sem rede/GPU). Ligue p/ embedar com o NeMo Retriever nv-embedqa de
    # verdade (catálogo build.nvidia.com com nvidia_api_key, ou NIM self-hosted/GPU).
    embeddings_use_nv: bool = Field(
        default=False, description="Embeddings da KB (F3.3) usam o NeMo Retriever nv-embedqa."
    )

    # Indexação da KB (F3.4): por padrão usa o índice in-memory offline/determinista (espinha
    # verde — a busca híbrida F3.5 roda/testa sem subir servidor). Ligue p/ indexar no Qdrant de
    # verdade (servidor em qdrant_url; dep qdrant-client). A KB NVIDIA e a coorte (F3.10) vivem em
    # coleções separadas — qdrant_collection é a da KB.
    index_use_qdrant: bool = Field(
        default=False, description="Indexação da KB (F3.4) usa o Qdrant (dense + sparse/BM25)."
    )
    qdrant_collection: str = Field(
        default="tapi_kb", description="Coleção Qdrant da KB NVIDIA (F3.4; coorte F3.10 à parte)."
    )

    # Reranking da busca híbrida (F3.6): por padrão usa o LexicalReranker offline/determinista
    # (espinha verde — reordena/testa sem rede/GPU). Ligue p/ reordenar com o NeMo Reranking NIM
    # nv-rerankqa de verdade (catálogo build.nvidia.com com nvidia_api_key, ou NIM self-hosted/GPU).
    reranker_use_nv: bool = Field(
        default=False, description="Reranking da busca (F3.6) usa o NeMo Reranking NIM nv-rerankqa."
    )
    # Provider do reranker real: nemo (default no build) | cohere (comparativo F7.4, ligado).
    reranker_provider: RerankerProvider = "nemo"
    cohere_api_key: str = Field(default="", description="Cohere Rerank — comparativo F7.4 (trial).")
    cohere_rerank_model: str = Field(
        default="rerank-multilingual-v3.0",
        description="Modelo Cohere Rerank (multilíngue p/ PT-BR; comparativo F7.4).",
    )

    # Avaliação RAGAS do RAG (F3.9): por padrão usa o LexicalRagasMetrics offline/determinista
    # (espinha verde — as 4 métricas rodam no CI/smoke RAGAS sem rede/GPU e geram o baseline
    # versionado). Ligue p/ avaliar com a biblioteca ragas + juiz Nemotron (catálogo
    # build.nvidia.com com nvidia_api_key). O run LLM-judged consolidado contra os limiares
    # (faithfulness ≥ 0,80; context recall ≥ 0,70) é a F7.3 — aqui o backend fica reservado.
    ragas_use_llm: bool = Field(
        default=False, description="Avaliação RAGAS (F3.9) usa a lib ragas + juiz Nemotron (F7.3)."
    )

    # --- Busca / scraping -------------------------------------------------------
    tavily_api_key: str = ""
    firecrawl_api_key: str = ""

    # scraper (F2.4): por padrão é offline (no-op limpo, espinha reproduzível sem rede).
    # Ligue p/ o nó coletar de verdade via adapters F1 (requer tavily/firecrawl + Playwright).
    scraper_use_network: bool = Field(
        default=False, description="scraper (F2.4) coleta as fontes de verdade (rede/F1)."
    )

    # Pula o Firecrawl (F1.2) e vai direto ao render local (Playwright + trafilatura, F1.3/F1.4)
    # no intent `clean`. Para rodar **sem crédito de Firecrawl**: o render é grátis/local e já é o
    # fallback do roteador (F1.7) — esta flag o torna o caminho primário, evitando a 1ª tentativa
    # ao Firecrawl esgotado (que atrasa e às vezes falha em vez de cair limpo). `article`/
    # `structured` já são trafilatura/bs4 (sem Firecrawl), então não dependem disto.
    scraper_force_render: bool = Field(
        default=False,
        description="scraper (F2.4) pula o Firecrawl e usa só o render local (F1.3) no clean.",
    )

    # --- HITL (F2.8) ------------------------------------------------------------
    # Por padrão o grafo roda **sem** pausa humana (espinha verde, M2/DoD). Ligue p/ o nó
    # human_review pausar antes do briefing: bloqueante no modo sync (single-company, exige
    # checkpointer/F2.2 p/ o interrupt→resume) e não-bloqueante no modo auto (batch/cohort,
    # F1.14 — só marca `needs_review`). O modo vem de `GraphState.hitl`, não daqui.
    hitl_enabled: bool = Field(
        default=False, description="human_review (F2.8) pausa p/ revisão humana antes do briefing."
    )

    # --- Guarda de orçamento de LLM por run (F2.11) -----------------------------
    # Os créditos grátis do build.nvidia.com têm rate limit; este teto **aborta a próxima
    # chamada** quando o run atinge o limite (os nós degradam p/ o determinista, sem estourar).
    # Off por default (espinha verde/M2); ligue + defina ao menos um teto (0 = sem teto naquela
    # dimensão). A guarda só arma se `llm_budget_enabled` e algum teto > 0.
    llm_budget_enabled: bool = Field(
        default=False, description="Guarda de orçamento de LLM por run (F2.11)."
    )
    llm_max_calls: int = Field(
        default=0, ge=0, description="Máx. de chamadas de LLM por run (0 = sem teto)."
    )
    llm_max_tokens: int = Field(
        default=0, ge=0, description="Máx. de tokens (in+out) por run (0 = sem teto)."
    )
    llm_max_cost_usd: float = Field(
        default=0.0, ge=0, description="Máx. de custo estimado por run em USD (0 = sem teto)."
    )

    # --- Hardening: timeout por chamada de LLM (F7.6) ---------------------------
    # Teto de tempo de PAREDE por completamento do Nemotron (geração). O `timeout` da lib
    # (langchain-nvidia-ai-endpoints) só cobre o poll após um 202; o socket de `session.post`
    # não tem teto, então uma conexão pendurada travaria o run. Este teto roda a chamada numa
    # thread e aborta a espera no estouro (`LLMTimeout`); os nós LLM (F2.5/F2.6/F4.2/F4.4) já
    # degradam p/ o caminho determinista a qualquer falha — sem alucinar. Sempre ativo no
    # caminho real (a espinha offline não chama o LLM, então não é afetada); 0 = sem teto.
    llm_request_timeout_seconds: float = Field(
        default=120.0,
        ge=0,
        description="Teto de tempo (s) por chamada de LLM (F7.6); 0 = sem teto.",
    )

    # Teto do **job RQ** por run (F2.10). O default do RQ é 180s — curto p/ um run real (coleta +
    # LLM com reasoning + retries do F7.6), morto no meio com `JobTimeoutException`. Generoso por
    # padrão p/ caber o caminho completo; 0 = sem teto (RQ `-1`).
    worker_job_timeout_seconds: int = Field(
        default=900, ge=0, description="Teto do job RQ por run em s (F2.10); 0 = sem teto."
    )

    # --- Cache de inferência LLM por prompt+modelo+versão (F2.14) ----------------
    # Cacheia a saída crua dos nós LLM (search_planner/extractor/classifier): poupa o rate
    # limit do free tier (complementa F2.11) e torna runs/eval REPRODUTÍVEIS. Invalida sozinho
    # quando o prompt muda (content_sha) ou a versão sobe (F0.12). NÃO cacheia scraping (frescor).
    # Off por default (espinha verde/M2); backend em disco (default) ou Redis (opt-in).
    llm_cache_enabled: bool = Field(
        default=False, description="Cache de inferência LLM por prompt+modelo+versão (F2.14)."
    )
    llm_cache_backend: CacheBackend = "disk"
    llm_cache_dir: str = Field(
        default=".cache/llm", description="Diretório do cache de LLM em disco (F2.14)."
    )
    llm_cache_ttl_seconds: int = Field(
        default=0, ge=0, description="Expiração do cache de LLM em s (0 = sem expiração)."
    )

    # --- Dados ------------------------------------------------------------------
    postgres_url: str = "postgresql://tapi:tapi@localhost:5432/tapi"
    qdrant_url: str = "http://localhost:6333"
    redis_url: str = "redis://localhost:6379/0"

    # --- Observabilidade --------------------------------------------------------
    langfuse_host: str = "http://localhost:3001"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""

    # --- Auth da ferramenta (gate interno — F5.9) -------------------------------
    tapi_api_token: str = ""

    # --- Idioma de saída (F0.13) ------------------------------------------------
    output_lang: str = Field(default="pt-BR", description="Idioma de briefing/recs/UI.")

    # --- CORS da API (F5.2 ↔ F5.3) ----------------------------------------------
    # O front roda noutra porta (3000) que a API (8080) = cross-origin; sem os cabeçalhos CORS
    # o browser BLOQUEIA a resposta mesmo com a API devolvendo 200. Lista separada por vírgula;
    # default = o front no dev local.
    cors_allow_origins: str = Field(
        default="http://localhost:3000",
        description="Origens CORS permitidas (separadas por vírgula) p/ a API (F5.2).",
    )

    # --- Derivados --------------------------------------------------------------
    @computed_field  # type: ignore[prop-decorator]
    @property
    def sqlalchemy_url(self) -> str:
        """URL do Postgres com driver psycopg v3 explícito (SQLModel/Alembic, F0.6)."""
        if self.postgres_url.startswith("postgresql+"):
            return self.postgres_url
        return self.postgres_url.replace("postgresql://", "postgresql+psycopg://", 1)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def langfuse_enabled(self) -> bool:
        """Tracing só liga com as duas chaves presentes (F0.8)."""
        return bool(self.langfuse_public_key and self.langfuse_secret_key)


@lru_cache
def get_settings() -> Settings:
    """Retorna a config (cacheada). Use isto em vez de instanciar `Settings()`."""
    return Settings()
