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
            logger.error("Erro na API Gemini/produto (tentativa %d/%d): %s", tentativa, _MAX_RETRIES, exc)
            return None
    return None


def resumir_produto(textos: list[str], nome_empresa: str) -> str | None:
    """Resume textos coletados do site em 1-2 frases descrevendo o produto principal."""
    conteudo = "\n\n".join(f"[Fonte {i+1}]\n{t}" for i, t in enumerate(textos) if t)
    if not conteudo.strip():
        return None

    prompt = (
        f"Com base nos trechos abaixo do site da empresa '{nome_empresa}', "
        "escreva UMA frase (máximo 2) descrevendo o produto ou serviço principal. "
        "Seja objetivo e use linguagem de negócios. "
        "Não reproduza slogans, chamadas de marketing ou frases genéricas — descreva concretamente o que o produto faz. "
        "Responda apenas a frase, sem explicações.\n\n"
        + conteudo
    )
    return _chamar_gemini(prompt)


def inferir_produto(nome_empresa: str, dominio: str) -> str | None:
    """Infere o produto da empresa a partir do conhecimento do modelo, sem conteúdo do site."""
    prompt = (
        f"Qual é o produto ou serviço principal da empresa '{nome_empresa}' "
        f"(domínio: {dominio})? "
        "Se você conhecer essa empresa, descreva em UMA frase objetiva o que ela oferece. "
        "Se não tiver certeza, responda exatamente: NAO_ENCONTRADO"
    )
    resultado = _chamar_gemini(prompt)
    if not resultado or resultado.upper() == "NAO_ENCONTRADO":
        return None
    return resultado
