"""Helper de chamada ao LLM via OpenRouter, compartilhado pelos agentes.

Centraliza a conexão para não repetir o código em cada agente.
"""

from __future__ import annotations

import os
import json

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def ask_llm(system_prompt: str, user_prompt: str, max_tokens: int = 800) -> str:
    """Manda um system + user prompt ao modelo e devolve o texto da resposta."""
    client = OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=os.getenv("OPENROUTER_API_KEY", "").strip(),
    )
    response = client.chat.completions.create(
        model=os.getenv("OPENROUTER_MODEL", "").strip(),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=max_tokens,
        temperature=0,  # determinístico: mesma entrada -> mesma saída (estabiliza a classificação)
        seed=0,  # reforça a reprodutibilidade (reduz a variância residual do provedor)
    )
    if not response.choices:
        return ""
    return response.choices[0].message.content or ""

def parse_json(text: str) -> dict:
    """Extrai um objeto JSON da resposta do LLM, tolerante a texto/fences em volta."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return {}
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
