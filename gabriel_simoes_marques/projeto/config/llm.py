import json
from groq import AsyncGroq, RateLimitError as GroqRateLimitError
from openai import AsyncOpenAI

from config.settings import settings

GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

OPENROUTER_MODELS = {
    "llama-3.3-70b": "meta-llama/llama-3.3-70b-instruct:free",
    "deepseek-r1": "deepseek/deepseek-r1:free",
    "gemma-3-27b": "google/gemma-3-27b-it:free",
    "qwen3-235b": "qwen/qwen3-235b-a22b:free",
    "mistral-7b": "mistralai/mistral-7b-instruct:free",
}

DEFAULT_MODEL = "llama-3.3-70b"


async def chat(
    messages: list[dict],
    model: str = DEFAULT_MODEL,
    max_tokens: int = 2048,
    json_mode: bool = True,
    temperature: float = 0.3,
) -> str:
    """
    Chama Groq primeiro (baixa latência). Se rate limit, cai pro OpenRouter.
    model: chave de OPENROUTER_MODELS ou model ID completo.
    """
    or_model = OPENROUTER_MODELS.get(model, model)
    response_format = {"type": "json_object"} if json_mode else None

    # tenta Groq primeiro
    try:
        groq = AsyncGroq(api_key=settings.groq_api_key)
        kwargs = dict(
            model=GROQ_MODEL,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = await groq.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""
    except GroqRateLimitError:
        pass  # fallback pro OpenRouter
    except Exception:
        pass  # qualquer erro no Groq → tenta OpenRouter

    # fallback OpenRouter
    or_client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
    )
    kwargs = dict(
        model=or_model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        extra_headers={"HTTP-Referer": "https://nvidia-radar.local"},
    )
    if json_mode:
        kwargs["response_format"] = response_format
    resp = await or_client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


async def chat_json(messages: list[dict], model: str = DEFAULT_MODEL, max_tokens: int = 2048, temperature: float = 0.3) -> dict:
    """Wrapper que faz parse do JSON automaticamente."""
    raw = await chat(messages, model=model, max_tokens=max_tokens, json_mode=True, temperature=temperature)
    return json.loads(raw)
