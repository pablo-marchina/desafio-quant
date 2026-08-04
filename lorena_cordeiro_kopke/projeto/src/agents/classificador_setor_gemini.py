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

_SETORES_VALIDOS = {
    "Fintech", "Healthtech", "Edtech", "Agritech", "Legaltech",
    "Proptech", "Insurtech", "Retailtech", "Logtech", "Govtech",
    "HRtech", "Martech", "Segurança", "Dados e Analytics", "Infraestrutura de IA",
    "Automação Industrial", "Varejo", "Saúde", "Educação", "Agronegócio",
    "Jurídico", "RH", "Marketing", "Logística", "Imóveis",
    "Seguros", "Governo", "Outro",
}


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
            logger.error("Erro na API Gemini/setor (tentativa %d/%d): %s", tentativa, _MAX_RETRIES, exc)
            return None
    return None


def classificar_setor(
    nome_empresa: str,
    cnae: str | None,
    produto: str | None,
    uso_ia: str | None,
) -> str | None:
    """Classifica o setor da empresa com base em CNAE, produto e uso de IA.

    Retorna um dos valores de _SETORES_VALIDOS ou None se não for possível determinar.
    """
    partes: list[str] = []
    if cnae:
        partes.append(f"CNAE principal: {cnae}")
    if produto:
        partes.append(f"Produto/serviço: {produto}")
    if uso_ia:
        partes.append(f"Como usa IA: {uso_ia}")

    if not partes:
        return None

    setores_lista = ", ".join(sorted(_SETORES_VALIDOS))
    prompt = (
        f"Com base nas informações abaixo sobre a empresa '{nome_empresa}', "
        "classifique em qual setor ela atua. "
        f"Escolha UMA opção da lista a seguir: {setores_lista}. "
        "Responda apenas com o nome do setor, sem explicações.\n\n"
        + "\n".join(partes)
    )

    resultado = _chamar_gemini(prompt)
    if not resultado:
        return None

    resultado_limpo = resultado.strip().strip(".")
    for setor in _SETORES_VALIDOS:
        if setor.lower() == resultado_limpo.lower():
            return setor

    # Tolerância: o modelo pode responder com variações próximas
    for setor in _SETORES_VALIDOS:
        if setor.lower() in resultado_limpo.lower():
            return setor

    return resultado_limpo or None
