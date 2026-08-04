import json
from typing import Any

import httpx

from app.settings import Settings


class LlmUnavailableError(RuntimeError):
    pass


def is_llm_enabled(settings: Settings) -> bool:
    return settings.model_provider == "openai" and bool(settings.openai_api_key)


def generate_openai_json(
    settings: Settings,
    system_prompt: str,
    user_prompt: str,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    if not is_llm_enabled(settings):
        raise LlmUnavailableError("OpenAI API key not configured")

    payload = {
        "model": settings.openai_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise LlmUnavailableError("OpenAI request failed") from exc

    content = response.json()["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("LLM response must be a JSON object")
    return parsed
