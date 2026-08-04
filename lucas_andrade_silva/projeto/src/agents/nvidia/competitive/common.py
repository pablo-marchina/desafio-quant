from __future__ import annotations

import json
import os
import re
from typing import Any

from groq import Groq

from rag.settings import required_env


def _extract_json(content: str) -> dict[str, Any]:
    content = re.sub(r"<think>.*?</think>\s*", "", content, flags=re.DOTALL).strip()
    try:
        value = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            raise ValueError("O modelo não retornou um objeto JSON")
        value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("O modelo não retornou um objeto JSON")
    return value


def call_json(system_prompt: str, payload: dict[str, Any]) -> dict[str, Any]:
    client = Groq(api_key=required_env("GROQ_API_KEY"))
    json_prompt = (
        f"{system_prompt}\n\n"
        "Responda exclusivamente com um objeto em formato json válido."
    )
    response = client.chat.completions.create(
        model=os.getenv("GROQ_COMPETITIVE_MODEL", "llama-3.3-70b-versatile"),
        messages=[
            {"role": "system", "content": json_prompt},
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False, indent=2),
            },
        ],
        temperature=0,
        max_completion_tokens=1400,
        response_format={"type": "json_object"},
    )
    return _extract_json(response.choices[0].message.content)
