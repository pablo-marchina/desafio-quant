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

# Modelo base (mais simples/barato). Se retornar INCERTO ou valor inválido,
# sobe para o modelo intermediário antes de desistir.
_MODEL_BASE = "gemini-flash-lite-latest"
_MODEL_FALLBACK = "gemini-flash-latest"

_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 5.0

# --------------------------------------------------------------------------
# Conjunto FECHADO de tipos válidos.
# Qualquer resposta fora deste conjunto é descartada (anti-alucinação).
# --------------------------------------------------------------------------
TIPOS_VALIDOS: frozenset[str] = frozenset({
    "NLP / LLM",
    "Visão Computacional",
    "Análise Preditiva",
    "IA Generativa",
    "Automação Inteligente",
    "Dados e Analytics",
})

_SENTINEL_INCERTO = "INCERTO"


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
                "Erro na API Gemini/ia_tipo (tentativa %d/%d): %s",
                tentativa, _MAX_RETRIES, exc,
            )
            return None
    return None


def _construir_prompt(nome_empresa: str, produto: str | None, uso_ia: str | None) -> str:
    # Lista exata de opções embutida no prompt para forçar resposta fechada
    tipos_lista = "\n".join(f"- {t}" for t in sorted(TIPOS_VALIDOS))
    partes: list[str] = []
    if produto:
        partes.append(f"Produto/serviço: {produto}")
    if uso_ia:
        partes.append(f"Como usa IA: {uso_ia}")
    contexto = "\n".join(partes) if partes else "(sem dados disponíveis)"

    return (
        f"Classifique o tipo principal de Inteligência Artificial usado pela empresa '{nome_empresa}'.\n\n"
        f"Informações disponíveis:\n{contexto}\n\n"
        "Responda com EXATAMENTE UMA das opções abaixo (copie o texto sem alterações):\n"
        f"{tipos_lista}\n\n"
        f"Regras obrigatórias:\n"
        f"- Escolha apenas com base nas informações fornecidas acima.\n"
        f"- Se as informações forem insuficientes para ter certeza, responda: {_SENTINEL_INCERTO}\n"
        f"- Não invente informações. Não adicione texto extra. Apenas a opção escolhida.\n"
        f"- Não use conhecimento externo sobre a empresa — classifique SOMENTE pelo texto acima."
    )


def _parse_tipo(resposta: str) -> str | None:
    """Valida a resposta contra o conjunto fechado. Retorna None se não bater.

    Esta função é a barreira anti-alucinação: qualquer texto que o modelo
    produza fora de TIPOS_VALIDOS é descartado silenciosamente.
    """
    candidato = resposta.strip()

    if candidato.upper() == _SENTINEL_INCERTO:
        return None

    # Correspondência exata (caminho esperado)
    if candidato in TIPOS_VALIDOS:
        return candidato

    # Correspondência case-insensitive como tolerância a variações de caixa
    candidato_lower = candidato.lower()
    for tipo in TIPOS_VALIDOS:
        if tipo.lower() == candidato_lower:
            return tipo

    # Resposta fora do conjunto → descarta (anti-alucinação)
    logger.warning(
        "Resposta fora do conjunto permitido (descartada): %r", candidato
    )
    return None


def classificar_ia_tipo(
    nome_empresa: str,
    produto: str | None = None,
    uso_ia: str | None = None,
) -> str | None:
    """Classifica o tipo principal de IA da empresa.

    Estratégia em dois níveis — usa o modelo mais barato primeiro e só
    aciona o modelo intermediário quando o resultado é incerto ou inválido:

      1. gemini-flash-lite-latest  → mais rápido e econômico
      2. gemini-flash-latest       → maior capacidade de raciocínio

    Anti-alucinação:
      - O prompt instrui o modelo a responder SOMENTE a partir dos dados
        fornecidos, sem usar conhecimento externo sobre a empresa.
      - A resposta é validada contra um conjunto fechado (TIPOS_VALIDOS).
      - Qualquer saída fora do conjunto é descartada, não armazenada.
      - Se ambos os modelos falharem ou retornarem INCERTO → retorna None.

    Returns:
        Um dos valores de TIPOS_VALIDOS, ou None se não for possível
        classificar com confiança.
    """
    if not produto and not uso_ia:
        logger.info("Sem dados suficientes para classificar ia_tipo de '%s'", nome_empresa)
        return None

    prompt = _construir_prompt(nome_empresa, produto, uso_ia)

    # Nível 1: modelo base
    resposta = _chamar_gemini(prompt, _MODEL_BASE)
    if resposta:
        resultado = _parse_tipo(resposta)
        if resultado is not None:
            return resultado
        logger.info(
            "Modelo base retornou INCERTO/inválido para '%s' — tentando fallback",
            nome_empresa,
        )

    # Nível 2: modelo intermediário (só acionado se o base falhou)
    resposta = _chamar_gemini(prompt, _MODEL_FALLBACK)
    if resposta:
        resultado = _parse_tipo(resposta)
        if resultado is not None:
            return resultado

    return None
