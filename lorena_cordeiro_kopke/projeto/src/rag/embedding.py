from __future__ import annotations

import logging
import os
from pathlib import Path

from google import genai

logger = logging.getLogger(__name__)

_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
if _ENV_PATH.exists():
    for _line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

_GEMINI_MODEL = "gemini-embedding-001"


def _get_gemini_client() -> genai.Client:
    if not hasattr(_get_gemini_client, "_instance"):
        api_key = os.environ.get("GEMINI_API_KEY2")
        if not api_key:
            raise EnvironmentError("GEMINI_API_KEY2 não configurada no .env")
        _get_gemini_client._instance = genai.Client(api_key=api_key)
    return _get_gemini_client._instance


def gerar_embedding(texto: str) -> list[float]:
    client = _get_gemini_client()
    result = client.models.embed_content(
        model=_GEMINI_MODEL,
        contents=texto,
    )
    return result.embeddings[0].values
