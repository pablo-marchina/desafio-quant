"""Clientes LLM com fallback multi-provedor para o Classifier Agent.

Ordem de prioridade:
  OpenRouter KEY_1 → OpenRouter KEY_2 → Ollama (local) → Groq → Gemini

Ollama vem antes de Groq/Gemini porque roda local sem rate limit/custo — bom
lugar pra cair quando os provedores pagos estão com saldo/quota esgotados.
Cada tentativa passa por retry seletivo (_with_retries/_is_transient): erros
transitórios (timeout, rate-limit momentâneo, resposta vazia) ganham até 3
tentativas com backoff exponencial; erros permanentes (chave inválida, sem
saldo, quota esgotada, modelo inexistente) falham imediato, sem retry.

Cada provider recebe o prompt completo (system + user em um único string) e
retorna uma string JSON bruta. A limpeza e parsing ficam em classifier.py.
"""
from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from ..config import get_settings
from ..logging_conf import get_logger

logger = get_logger("agents.llm")

# ---------------------------------------------------------------------------
# Tipos
# ---------------------------------------------------------------------------

ProviderFn = Callable[[str, str], Awaitable[str]]  # (system_prompt, user_prompt) → JSON str


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _openai_client(base_url: str, api_key: str):
    """Cria AsyncOpenAI lazy (evita import global desnecessário)."""
    from openai import AsyncOpenAI
    return AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=60.0)


async def _call_openai_compat(
    base_url: str,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    json_mode: bool = True,
) -> str:
    client = _openai_client(base_url, api_key)
    kwargs: dict[str, Any] = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
        max_tokens=512,
        **kwargs,
    )
    await client.close()
    return resp.choices[0].message.content or ""


async def _call_gemini(
    system_prompt: str, user_prompt: str, json_mode: bool = True
) -> str:
    from google import genai
    from google.genai import types

    cfg = get_settings()
    client = genai.Client(api_key=cfg.gemini_api_key)
    full_prompt = f"{system_prompt}\n\n{user_prompt}"
    config_kwargs: dict[str, Any] = {"temperature": 0.0}
    if json_mode:
        config_kwargs["response_mime_type"] = "application/json"
    resp = await client.aio.models.generate_content(
        model=cfg.gemini_model,
        contents=full_prompt,
        config=types.GenerateContentConfig(**config_kwargs),
    )
    return resp.text or ""


async def _check_ollama_ready(cfg) -> None:
    """Verifica se o Ollama esta acessivel e com o modelo configurado
    disponivel. Nao tenta subir o servico via subprocess — ambientes tipicos
    rodam o Ollama como servico gerenciado (systemd, etc); fazer isso a partir
    do processo Python seria fragil. Se o modelo nao estiver baixado, tenta um
    'ollama pull' (idempotente e seguro); se o servico estiver totalmente
    inacessivel, levanta um erro claro e acionavel."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{cfg.ollama_base_url}/api/tags")
            resp.raise_for_status()
            models = {m["name"] for m in resp.json().get("models", [])}
    except Exception as exc:
        raise RuntimeError(
            f"Ollama nao esta respondendo em {cfg.ollama_base_url} — inicie o servico "
            f"('systemctl start ollama' ou 'ollama serve') antes de usar este provedor. Detalhe: {exc}"
        ) from exc

    if cfg.ollama_model not in models:
        logger.warning(
            "Modelo '%s' nao encontrado no Ollama — tentando 'ollama pull %s'...",
            cfg.ollama_model, cfg.ollama_model,
        )
        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                resp = await client.post(
                    f"{cfg.ollama_base_url}/api/pull", json={"name": cfg.ollama_model, "stream": False}
                )
                resp.raise_for_status()
        except Exception as exc:
            raise RuntimeError(
                f"Modelo '{cfg.ollama_model}' indisponivel e o pull automatico falhou: {exc}"
            ) from exc


async def _call_ollama(
    system_prompt: str, user_prompt: str, json_mode: bool = True
) -> str:
    cfg = get_settings()
    await _check_ollama_ready(cfg)
    payload: dict[str, Any] = {
        "model": cfg.ollama_model,
        "prompt": f"{system_prompt}\n\n{user_prompt}",
        "stream": False,
        "options": {"temperature": 0},
    }
    if json_mode:
        payload["format"] = "json"
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(f"{cfg.ollama_base_url}/api/generate", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "")


# ---------------------------------------------------------------------------
# Retry seletivo (transitório vs. permanente)
# ---------------------------------------------------------------------------

def _is_transient(exc: Exception) -> bool:
    """Erros que valem retry (timeout, rate-limit momentaneo, resposta vazia)
    vs. erros permanentes (chave invalida, sem saldo, quota esgotada, modelo
    inexistente) — repetir esses ultimos so adia uma falha inevitavel."""
    msg = str(exc).lower()
    if any(p in msg for p in ("resource_exhausted", "quota", "insufficient", "401", "402", "403", "404")):
        return False
    if isinstance(exc, (httpx.TimeoutException, asyncio.TimeoutError)):
        return True
    if "resposta vazia" in msg or "429" in msg or "503" in msg or "502" in msg or "500" in msg or "rate" in msg or "timeout" in msg:
        return True
    return False


async def _with_retries(
    fn: ProviderFn, system_prompt: str, user_prompt: str, retries: int = 3, base_delay: float = 1.0
) -> str:
    """Tenta fn ate `retries` vezes com backoff exponencial (1s, 2s, 4s),
    mas so para falhas transitorias — ver _is_transient."""
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            result = await fn(system_prompt, user_prompt)
            if result:
                return result
            raise ValueError("Resposta vazia do provedor")
        except Exception as exc:
            last_exc = exc
            if not _is_transient(exc) or attempt == retries - 1:
                raise
            delay = base_delay * (2 ** attempt)
            logger.warning("Tentativa %d/%d falhou (%s) — nova tentativa em %.0fs...", attempt + 1, retries, exc, delay)
            await asyncio.sleep(delay)
    raise last_exc  # inalcancavel na pratica


# ---------------------------------------------------------------------------
# Tabela de providers
# ---------------------------------------------------------------------------

def _build_providers() -> list[tuple[str, ProviderFn]]:
    cfg = get_settings()
    providers: list[tuple[str, ProviderFn]] = []

    if cfg.openrouter_api_key_1:
        async def _or1(sp: str, up: str) -> str:
            return await _call_openai_compat(
                "https://openrouter.ai/api/v1", cfg.openrouter_api_key_1, cfg.openrouter_model, sp, up
            )
        providers.append(("openrouter_key1", _or1))

    if cfg.openrouter_api_key_2:
        async def _or2(sp: str, up: str) -> str:
            return await _call_openai_compat(
                "https://openrouter.ai/api/v1", cfg.openrouter_api_key_2, cfg.openrouter_model, sp, up
            )
        providers.append(("openrouter_key2", _or2))

    # Ollama antes de Groq/Gemini: roda local, sem rate limit/custo — bom
    # lugar pra cair quando os provedores pagos estao com saldo/quota esgotados.
    providers.append(("ollama", _call_ollama))

    if cfg.groq_api_key:
        async def _groq(sp: str, up: str) -> str:
            return await _call_openai_compat(
                "https://api.groq.com/openai/v1", cfg.groq_api_key, cfg.groq_model, sp, up
            )
        providers.append(("groq", _groq))

    if cfg.gemini_api_key:
        providers.append(("gemini", _call_gemini))

    return providers


_PROVIDERS: list[tuple[str, ProviderFn]] | None = None


def get_providers() -> list[tuple[str, ProviderFn]]:
    global _PROVIDERS
    if _PROVIDERS is None:
        _PROVIDERS = _build_providers()
    return _PROVIDERS


# ---------------------------------------------------------------------------
# Fallback principal
# ---------------------------------------------------------------------------

async def classify_with_fallback(
    system_prompt: str,
    user_prompt: str,
    startup_id: int,
    force_provider: str | None = None,
) -> tuple[str, str]:
    """Tenta provedores em ordem e retorna (raw_json, provider_label).

    Se force_provider for passado no formato 'provider:model', usa apenas
    aquele provedor ignorando a cadeia de fallback.
    """
    cfg = get_settings()

    if force_provider:
        provider_name, _, model_override = force_provider.partition(":")
        provider_name = provider_name.lower()
        result = await _call_forced(provider_name, model_override or None, system_prompt, user_prompt, cfg)
        return result, force_provider

    providers = get_providers()
    if not providers:
        raise RuntimeError("Nenhum provedor LLM configurado. Defina ao menos uma API key no .env.")

    last_exc: Exception | None = None
    for label, fn in providers:
        t0 = time.monotonic()
        try:
            result = await _with_retries(fn, system_prompt, user_prompt)
            elapsed_ms = (time.monotonic() - t0) * 1000
            logger.info("✅ LLM respondeu via %s em %.0fms (startup %d)", label, elapsed_ms, startup_id)
            return result, label
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "Rotacao LLM [%s] para startup %d: %s",
                label, startup_id, exc,
            )

    raise RuntimeError(f"Todos os provedores LLM falharam. Ultimo erro: {last_exc}")


async def _call_text_provider(
    label: str,
    system_prompt: str,
    user_prompt: str,
) -> str:
    """Chama um provider sem JSON mode — retorna texto livre."""
    cfg = get_settings()
    if label in ("openrouter_key1", "openrouter_key2"):
        key = cfg.openrouter_api_key_1 if label == "openrouter_key1" else cfg.openrouter_api_key_2
        if not key:
            raise ValueError(f"{label} sem chave configurada.")
        return await _call_openai_compat(
            "https://openrouter.ai/api/v1", key, cfg.openrouter_model,
            system_prompt, user_prompt, json_mode=False,
        )
    if label == "groq":
        if not cfg.groq_api_key:
            raise ValueError("GROQ_API_KEY não configurada.")
        return await _call_openai_compat(
            "https://api.groq.com/openai/v1", cfg.groq_api_key, cfg.groq_model,
            system_prompt, user_prompt, json_mode=False,
        )
    if label == "gemini":
        return await _call_gemini(system_prompt, user_prompt, json_mode=False)
    if label == "ollama":
        return await _call_ollama(system_prompt, user_prompt, json_mode=False)
    raise ValueError(f"Provider desconhecido: {label!r}")


async def generate_text_with_fallback(
    system_prompt: str,
    user_prompt: str,
    context_label: str = "",
) -> tuple[str, str]:
    """Gera texto livre (sem JSON mode) com a mesma cadeia de fallback do classificador.

    Retorna (texto_gerado, provider_label).
    """
    providers = get_providers()
    if not providers:
        raise RuntimeError("Nenhum provedor LLM configurado. Defina ao menos uma API key no .env.")

    last_exc: Exception | None = None
    for label, _ in providers:
        t0 = time.monotonic()
        try:
            text_fn: ProviderFn = lambda sp, up, _label=label: _call_text_provider(_label, sp, up)
            text = await _with_retries(text_fn, system_prompt, user_prompt)
            elapsed_ms = (time.monotonic() - t0) * 1000
            logger.info("✅ LLM (texto) respondeu via %s em %.0fms ('%s')", label, elapsed_ms, context_label)
            return text.strip(), label
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "Rotacao LLM texto [%s] para '%s': %s",
                label, context_label, exc,
            )

    raise RuntimeError(f"Todos os provedores LLM falharam para geração de texto. Último erro: {last_exc}")


async def _call_forced(
    provider: str,
    model: str | None,
    system_prompt: str,
    user_prompt: str,
    cfg,
) -> str:
    """Chama um provedor específico com modelo opcional."""
    if provider == "openrouter":
        key = cfg.openrouter_api_key_1 or cfg.openrouter_api_key_2
        if not key:
            raise ValueError("OPENROUTER_API_KEY_1 ou _2 não configurada.")
        return await _call_openai_compat(
            "https://openrouter.ai/api/v1", key, model or cfg.openrouter_model, system_prompt, user_prompt
        )
    if provider == "groq":
        if not cfg.groq_api_key:
            raise ValueError("GROQ_API_KEY não configurada.")
        return await _call_openai_compat(
            "https://api.groq.com/openai/v1", cfg.groq_api_key, model or cfg.groq_model, system_prompt, user_prompt
        )
    if provider == "gemini":
        if not cfg.gemini_api_key:
            raise ValueError("GEMINI_API_KEY não configurada.")
        from google import genai as _genai
        from google.genai import types as _types
        _client = _genai.Client(api_key=cfg.gemini_api_key)
        full = f"{system_prompt}\n\n{user_prompt}"
        resp = await _client.aio.models.generate_content(
            model=model or cfg.gemini_model,
            contents=full,
            config=_types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0,
            ),
        )
        return resp.text or ""
    if provider == "ollama":
        await _check_ollama_ready(cfg)
        payload = {
            "model": model or cfg.ollama_model,
            "prompt": f"{system_prompt}\n\n{user_prompt}",
            "format": "json",
            "stream": False,
            "options": {"temperature": 0},
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{cfg.ollama_base_url}/api/generate", json=payload)
            resp.raise_for_status()
            return resp.json().get("response", "")
    raise ValueError(f"Provedor desconhecido: '{provider}'. Use: openrouter, groq, gemini, ollama")
