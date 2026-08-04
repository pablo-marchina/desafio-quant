"""Abstração da camada de LLM.

Provider padrão: OpenAI (`gpt-4o-mini`), escolhido por custo. Em vez de
espalhar `ChatOpenAI(...)` pelos agentes, todos pedem o modelo aqui. Trocar
de provider vira uma mudança de UMA variável de ambiente (`LLM_PROVIDER`),
sem tocar em nenhum agente — o suporte a Anthropic continua disponível caso
seja necessário voltar.

Decisão didática: mantemos a mecânica explícita (um if por provider) em
vez de uma fábrica mágica, para que fique claro o que cada provider exige.
"""
from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel

from core.config import settings


@lru_cache
def get_llm(temperature: float = 0.0) -> BaseChatModel:
    """Retorna o chat model configurado via `LLM_PROVIDER`.

    Cada agente chama `get_llm()` e recebe o modelo certo já configurado.
    Falha cedo e com mensagem clara se a chave não estiver presente —
    "tratamento de erro explícito" é boa prática
    """
    provider = settings.llm_provider

    if provider == "anthropic":
        if not settings.anthropic_api_key:
            raise RuntimeError(
                "LLM_PROVIDER=anthropic mas ANTHROPIC_API_KEY está vazio. "
                "Preencha no .env."
            )
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=settings.anthropic_model,
            api_key=settings.anthropic_api_key,
            temperature=temperature,
        )

    if provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError(
                "LLM_PROVIDER=openai mas OPENAI_API_KEY está vazio. "
                "Preencha no .env."
            )
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=temperature,
        )

    raise ValueError(f"LLM_PROVIDER desconhecido: {provider!r}")
