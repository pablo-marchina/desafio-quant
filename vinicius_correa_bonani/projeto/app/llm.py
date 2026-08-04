"""Cliente LLM do projeto — provedor selecionável (NVIDIA NIM | Groq | OpenAI).

`chat()` monta o cliente do provedor ativo (ver `settings.llm_provider`):
- **NVIDIA NIM** (`ChatNVIDIA`, `langchain_nvidia_ai_endpoints`) quando há `NVIDIA_API_KEY`;
- **Groq/OpenAI** (`ChatOpenAI`, compatível com a API da OpenAI) caso contrário.

Todos os nós usam este helper — trocar de provedor é só config, sem tocar nós.
`chat_structured` centraliza o `method` do structured output, que varia por provedor
(Groq/OpenAI = `json_schema`; NVIDIA/Llama = `function_calling`, melhor suportado).
"""

from langchain_openai import ChatOpenAI

from app.config import settings


def chat(temperature: float = 0.0):
    """Cliente de chat do provedor ativo. Mesma assinatura para todos os nós."""
    if settings.llm_provider == "nvidia":
        from langchain_nvidia_ai_endpoints import ChatNVIDIA  # lazy: só quando usado

        client = ChatNVIDIA(
            model=settings.llm_model,
            api_key=settings.nvidia_api_key,
            temperature=temperature,
        )
        # o tier grátis da NVIDIA é lento (cold start/fila); sobe o timeout do cliente
        # interno (a lib não expõe knob público nesta versão).
        client._client.timeout = settings.nvidia_timeout
        return client
    return ChatOpenAI(
        model=settings.llm_model,
        temperature=temperature,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        # espera e repete no 429 (rate limit) em vez de derrubar o pipeline
        max_retries=settings.llm_max_retries,
    )


def chat_structured(schema, temperature: float = 0.0):
    """Structured output com o `method` certo para o provedor ativo.

    Groq/OpenAI usam `json_schema` (o `function_calling` da Groq é flaky); os modelos
    NVIDIA/Llama via NIM funcionam melhor com `function_calling`.
    """
    method = "json_schema" if settings.llm_provider in ("groq", "openai") else "function_calling"
    return chat(temperature).with_structured_output(schema, method=method)
