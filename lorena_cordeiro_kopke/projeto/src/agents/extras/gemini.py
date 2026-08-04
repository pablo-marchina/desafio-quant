from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path

from google import genai

logger = logging.getLogger(__name__)

_ENV_PATH = Path(__file__).resolve().parent.parent.parent.parent / ".env"
if _ENV_PATH.exists():
    for _line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

_GEMINI_CHAT_MODEL = "gemini-2.5-flash"
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 5.0

_client_primary: genai.Client | None = None
_client_fallback: genai.Client | None = None
_client_lock = threading.Lock()


def _get_clients() -> tuple[genai.Client, genai.Client | None]:
    global _client_primary, _client_fallback
    if _client_primary is None:
        with _client_lock:
            if _client_primary is None:
                api_key = os.environ.get("GEMINI_API_KEY")
                if not api_key:
                    raise EnvironmentError("GEMINI_API_KEY não configurada no .env")
                _client_primary = genai.Client(api_key=api_key)

                api_key2 = os.environ.get("GEMINI_API_KEY2")
                if api_key2:
                    _client_fallback = genai.Client(api_key=api_key2)
    return _client_primary, _client_fallback


def _is_quota_error(exc: Exception) -> bool:
    return "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc)


def chamar_gemini(prompt: str) -> str:
    """Chama o Gemini com retry exponencial. Usa GEMINI_API_KEY2 como fallback em caso de cota esgotada."""
    primary, fallback = _get_clients()
    last_exc: Exception | None = None

    for tentativa in range(1, _MAX_RETRIES + 1):
        try:
            response = primary.models.generate_content(
                model=_GEMINI_CHAT_MODEL,
                contents=prompt,
            )
            return (response.text or "").strip()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if _is_quota_error(exc) and fallback is not None:
                logger.warning(
                    "Gemini principal com cota esgotada (tentativa %d/%d) — tentando chave fallback",
                    tentativa, _MAX_RETRIES,
                )
                try:
                    response = fallback.models.generate_content(
                        model=_GEMINI_CHAT_MODEL,
                        contents=prompt,
                    )
                    return (response.text or "").strip()
                except Exception as exc2:  # noqa: BLE001
                    last_exc = exc2
                    logger.warning(
                        "Gemini fallback também falhou (tentativa %d/%d): %s",
                        tentativa, _MAX_RETRIES, exc2,
                    )
            else:
                if tentativa < _MAX_RETRIES:
                    delay = _RETRY_BASE_DELAY * (2 ** (tentativa - 1))
                    logger.warning(
                        "Gemini erro (tentativa %d/%d) — aguardando %.0fs: %s",
                        tentativa, _MAX_RETRIES, delay, exc,
                    )
                    time.sleep(delay)

    raise RuntimeError(f"Gemini falhou após {_MAX_RETRIES} tentativas") from last_exc
