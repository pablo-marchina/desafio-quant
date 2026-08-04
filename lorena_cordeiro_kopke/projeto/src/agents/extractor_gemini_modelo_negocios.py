from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import httpx
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
if _ENV_PATH.exists():
    for _line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

_MODEL = "gemini-flash-lite-latest"
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 5.0
_MODELOS_VALIDOS = {"B2B", "B2C", "B2B2C"}


def _get_client() -> genai.Client:
    if not hasattr(_get_client, "_instance"):
        api_key = os.environ.get("GEMINI_API_KEY2")
        if not api_key:
            raise EnvironmentError("GEMINI_API_KEY2 não configurada no .env")
        http = httpx.Client(verify=False)
        _get_client._instance = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(httpx_client=http),
        )
    return _get_client._instance


def _chamar_gemini(prompt: str) -> str | None:
    try:
        client = _get_client()
    except EnvironmentError as exc:
        logger.warning("Gemini indisponível: %s", exc)
        return None

    for tentativa in range(1, _MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(model=_MODEL, contents=prompt)
            return (response.text or "").strip() or None
        except Exception as exc:  # noqa: BLE001
            code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
            if code == 429 and tentativa < _MAX_RETRIES:
                delay = _RETRY_BASE_DELAY * (2 ** (tentativa - 1))
                logger.warning("Rate limit (429). Tentativa %d/%d — aguardando %.0fs.", tentativa, _MAX_RETRIES, delay)
                time.sleep(delay)
                continue
            logger.error("Erro na API Gemini/modelo_negocio (tentativa %d/%d): %s", tentativa, _MAX_RETRIES, exc)
            return None
    return None


def _parse_modelo(texto: str) -> str | None:
    upper = texto.strip().upper()
    for m in _MODELOS_VALIDOS:
        if m in upper:
            return m
    return None


def classificar_modelo_negocio(contextos: list[str], nome_empresa: str) -> str | None:
    """Classifica o modelo de negócio (B2B/B2C/B2B2C) com base em textos coletados.

    Retorna 'B2B', 'B2C', 'B2B2C' ou None se não for possível determinar.
    """
    conteudo = "\n\n".join(f"[Fonte {i+1}]\n{t}" for i, t in enumerate(contextos) if t)
    if not conteudo.strip():
        return None

    prompt = (
        f"Com base nas informações abaixo sobre a empresa '{nome_empresa}', "
        "classifique o modelo de negócio. "
        "Responda com UMA das opções: B2B, B2C ou B2B2C. Sem explicações.\n\n"
        + conteudo
    )
    resultado = _chamar_gemini(prompt)
    if not resultado:
        return None
    return _parse_modelo(resultado)


def inferir_modelo_negocio(nome_empresa: str, dominio: str) -> str | None:
    """Infere o modelo de negócio a partir do conhecimento do modelo, sem conteúdo do site.

    Retorna 'B2B', 'B2C', 'B2B2C' ou None se incerto.
    """
    prompt = (
        f"Qual o modelo de negócio da empresa '{nome_empresa}' (domínio: {dominio})? "
        "Responda com UMA das opções: B2B, B2C, B2B2C ou INCERTO. Sem explicações."
    )
    resultado = _chamar_gemini(prompt)
    if not resultado or "INCERTO" in resultado.upper():
        return None
    return _parse_modelo(resultado)
