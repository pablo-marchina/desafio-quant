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
        http = httpx.Client(verify=False)
        _get_client._instance = genai.Client(
            http_options=types.HttpOptions(httpx_client=http)
        )
    return _get_client._instance


def _chamar_gemini(prompt: str) -> str | None:
    client = _get_client()
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
            logger.error("Erro na API Gemini (tentativa %d/%d): %s", tentativa, _MAX_RETRIES, exc)
            return None
    return None


def resumir_uso_ia(textos: list[str], nome_empresa: str) -> str | None:
    """Resume textos coletados do site em 1-2 frases descrevendo como a empresa usa IA."""
    conteudo = "\n\n".join(f"[Fonte {i+1}]\n{t}" for i, t in enumerate(textos) if t)
    if not conteudo.strip():
        return None

    prompt = (
        f"Com base nos trechos abaixo do site da empresa '{nome_empresa}', "
        "escreva UMA frase (máximo 2) descrevendo como a empresa utiliza inteligência artificial "
        "no seu produto ou serviço. Seja objetivo e use linguagem de negócios. "
        "Responda apenas a frase, sem explicações.\n\n"
        + conteudo
    )
    resultado = _chamar_gemini(prompt)
    if resultado and resultado.upper() == "NAO_ENCONTRADO":
        return None
    return resultado


def inferir_uso_ia(nome_empresa: str, dominio: str) -> str | None:
    """Infere como a empresa usa IA a partir do conhecimento do modelo, sem conteúdo do site.

    Retorna None se o modelo não reconhecer a empresa ou não souber sobre o uso de IA.
    """
    prompt = (
        f"Como a empresa '{nome_empresa}' (domínio: {dominio}) utiliza inteligência artificial "
        "no seu produto ou serviço? "
        "Se você conhecer essa empresa, descreva em UMA frase objetiva o uso de IA. "
        "Se não tiver certeza, responda exatamente: NAO_ENCONTRADO"
    )
    resultado = _chamar_gemini(prompt)
    if not resultado or resultado.upper() == "NAO_ENCONTRADO":
        return None
    return resultado


def classificar_ia_core(contextos: list[str], nome_empresa: str) -> bool | None:
    """Classifica se IA é o core product da empresa com base em textos coletados.

    Retorna True se IA é o produto principal, False se é apenas uma ferramenta/feature,
    None se não for possível determinar.
    """
    conteudo = "\n\n".join(f"[Fonte {i+1}]\n{t}" for i, t in enumerate(contextos) if t)
    if not conteudo.strip():
        return None

    prompt = (
        f"Com base nas informações abaixo sobre a empresa '{nome_empresa}', determine se a "
        "Inteligência Artificial é o PRODUTO PRINCIPAL (core product) — ou seja, a IA em si "
        "é o que a empresa vende, e não apenas uma ferramenta usada internamente.\n\n"
        "Responda com uma única palavra: VERDADEIRO ou FALSO.\n\n"
        + conteudo
    )
    resultado = _chamar_gemini(prompt)
    if not resultado:
        return None
    token = resultado.strip().upper()
    if token == "VERDADEIRO":
        return True
    if token == "FALSO":
        return False
    # Aceita variações em caso de resposta extendida
    if "VERDADEIRO" in token:
        return True
    if "FALSO" in token:
        return False
    return None


def inferir_ia_core(nome_empresa: str, dominio: str) -> bool | None:
    """Infere se IA é o core product a partir do conhecimento do modelo, sem conteúdo do site.

    Retorna True, False ou None se incerto.
    """
    prompt = (
        f"A empresa '{nome_empresa}' (domínio: {dominio}) vende Inteligência Artificial como "
        "produto principal (core product)? Ou seja, a IA em si é o que a empresa oferece, "
        "e não apenas uma ferramenta interna?\n"
        "Se você conhecer essa empresa, responda com uma única palavra: VERDADEIRO ou FALSO.\n"
        "Se não tiver certeza, responda exatamente: INCERTO"
    )
    resultado = _chamar_gemini(prompt)
    if not resultado:
        return None
    token = resultado.strip().upper()
    if token == "INCERTO" or "INCERTO" in token:
        return None
    if token == "VERDADEIRO" or "VERDADEIRO" in token:
        return True
    if token == "FALSO" or "FALSO" in token:
        return False
    return None
