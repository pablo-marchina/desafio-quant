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
_MERCADOS_VALIDOS = {"Brasil", "LATAM", "Global"}


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
            logger.error("Erro na API Gemini/mercado_alvo (tentativa %d/%d): %s", tentativa, _MAX_RETRIES, exc)
            return None
    return None


def _parse_mercado(texto: str) -> str | None:
    upper = texto.strip().upper()
    if "BRASIL" in upper:
        return "Brasil"
    if "LATAM" in upper or "LATINA" in upper or "LATIN" in upper:
        return "LATAM"
    if "GLOBAL" in upper or "MUNDIAL" in upper or "WORLDWIDE" in upper:
        return "Global"
    return None


def inferir_mercado_alvo(
    nome_empresa: str,
    tld: str,
    produto: str | None = None,
    uso_ia: str | None = None,
    idioma_site: str | None = None,
) -> str | None:
    """Infere o mercado-alvo geográfico da empresa (Brasil / LATAM / Global).

    Recebe sinais já coletados: TLD do domínio, produto, uso_ia_descricao
    e, opcionalmente, o idioma detectado na homepage.
    """
    partes: list[str] = [f"TLD do domínio: {tld}"]
    if produto:
        partes.append(f"Produto/serviço: {produto}")
    if uso_ia:
        partes.append(f"Como usa IA: {uso_ia}")
    if idioma_site:
        partes.append(f"Idioma do site: {idioma_site}")

    prompt = (
        f"Com base nas informações abaixo sobre a empresa '{nome_empresa}', "
        "determine o mercado-alvo geográfico principal. "
        "Responda com UMA das opções: Brasil, LATAM ou Global. Sem explicações.\n\n"
        "Critérios:\n"
        "- Brasil: atende principalmente o mercado brasileiro\n"
        "- LATAM: atende América Latina (além do Brasil)\n"
        "- Global: atende mercados internacionais além da América Latina\n\n"
        + "\n".join(partes)
    )

    resultado = _chamar_gemini(prompt)
    if not resultado:
        return None
    return _parse_mercado(resultado)
