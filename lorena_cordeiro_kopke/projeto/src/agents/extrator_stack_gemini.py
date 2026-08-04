from __future__ import annotations

import json
import logging
import os
import re
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

_MODEL_BASE = "gemini-flash-lite-latest"
_MODEL_FALLBACK = "gemini-flash-latest"

_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 5.0


def _get_client() -> genai.Client:
    if not hasattr(_get_client, "_instance"):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError("GEMINI_API_KEY não configurada no .env")
        http = httpx.Client(verify=False)
        _get_client._instance = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(httpx_client=http),
        )
    return _get_client._instance


def _chamar_gemini(prompt: str, model: str) -> str | None:
    try:
        client = _get_client()
    except EnvironmentError as exc:
        logger.warning("Gemini indisponível: %s", exc)
        return None

    for tentativa in range(1, _MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(model=model, contents=prompt)
            return (response.text or "").strip() or None
        except Exception as exc:  # noqa: BLE001
            code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
            if code == 429 and tentativa < _MAX_RETRIES:
                delay = _RETRY_BASE_DELAY * (2 ** (tentativa - 1))
                logger.warning(
                    "Rate limit (429). Tentativa %d/%d — aguardando %.0fs.",
                    tentativa, _MAX_RETRIES, delay,
                )
                time.sleep(delay)
                continue
            logger.error(
                "Erro na API Gemini/stack (tentativa %d/%d): %s",
                tentativa, _MAX_RETRIES, exc,
            )
            return None
    return None


def _parsear_json(texto: str) -> dict | None:
    limpo = texto.strip()
    if limpo.startswith("```"):
        limpo = re.sub(r"^```(?:json)?\s*", "", limpo)
        limpo = re.sub(r"\s*```$", "", limpo)
    try:
        return json.loads(limpo)
    except json.JSONDecodeError:
        return None


def _construir_prompt(nome_empresa: str, titulos: list[str]) -> str:
    lista = "\n".join(f"- {t}" for t in titulos)
    return (
        f"Analise as vagas de emprego abaixo da startup '{nome_empresa}' "
        f"e extraia a stack técnica em uso.\n\n"
        f"Vagas:\n{lista}\n\n"
        "Foque em frameworks de ML/IA, linguagens de programação, provedores de cloud, "
        "orquestradores e ferramentas de MLOps mencionadas explicitamente nos títulos.\n\n"
        "Responda APENAS em JSON válido, sem texto adicional:\n"
        '{"frameworks_ml": [], "linguagens": [], "cloud": [], "orquestradores": [], "mlops": [], "outros": []}\n\n'
        "Se os títulos não revelarem stack técnica suficiente, responda exatamente:\n"
        '{"insuficiente": true}'
    )


def extrair_stack(nome_empresa: str, titulos: list[str]) -> dict | None:
    """Extrai stack técnica a partir de títulos de vagas via Gemini.

    Returns:
        Dict com categorias de stack, ou None se insuficiente/erro.
    """
    if not titulos:
        return None

    prompt = _construir_prompt(nome_empresa, titulos)

    for model in (_MODEL_BASE, _MODEL_FALLBACK):
        resposta = _chamar_gemini(prompt, model)
        if not resposta:
            continue
        resultado = _parsear_json(resposta)
        if resultado is None:
            logger.warning("JSON inválido retornado pelo Gemini para '%s'", nome_empresa)
            continue
        if resultado.get("insuficiente"):
            return None
        # Descarta resultado sem nenhuma categoria preenchida
        tem_dados = any(
            resultado.get(k) for k in ("frameworks_ml", "linguagens", "cloud", "orquestradores", "mlops", "outros")
        )
        if tem_dados:
            return resultado
        logger.info("Modelo base sem dados suficientes para '%s' — tentando fallback", nome_empresa)

    return None
