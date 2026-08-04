"""Teste de conexão com o OpenRouter (Bloco 0 — Fundação).

Lê as variáveis do .env, faz uma chamada mínima ao modelo configurado via
OpenRouter (que é compatível com a API da OpenAI) e imprime a resposta.
Serve apenas para validar que o acesso ao LLM funciona — não é lógica de negócio.

Uso:
    uv run python scripts/check_openrouter.py
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

# O OpenRouter expõe uma API compatível com a da OpenAI nesta URL base.
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def main() -> int:
    load_dotenv()

    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    model = os.getenv("OPENROUTER_MODEL", "").strip()

    # Validação amigável antes de gastar uma chamada de API.
    missing = [
        name
        for name, value in (
            ("OPENROUTER_API_KEY", api_key),
            ("OPENROUTER_MODEL", model),
        )
        if not value
    ]
    if missing:
        print(f"[ERRO] Variáveis ausentes no .env: {', '.join(missing)}")
        print("Preencha-as no .env e rode de novo.")
        return 1

    print(f"Conectando ao OpenRouter (modelo: {model})...")
    client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=api_key)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Responda apenas com a palavra: ok"}],
            max_tokens=128,
        )
    except OpenAIError as exc:
        print(f"[FALHA] Erro ao chamar o OpenRouter: {exc}")
        return 1

    # O OpenRouter pode devolver status de sucesso porém sem 'choices' quando o
    # provedor do modelo (sobretudo os :free) falha. Não é erro de conexão.
    if not response.choices:
        detail = getattr(response, "error", None)
        if detail is None:
            extra = getattr(response, "model_extra", None) or {}
            detail = extra.get("error", extra) or "sem detalhes"
        print("[FALHA] O OpenRouter respondeu sem 'choices' (provedor sem retorno).")
        print(f"        Detalhe: {detail}")
        print("        A conexao funciona; isso e instabilidade do modelo :free.")
        return 1

    message = response.choices[0].message
    content = message.content
    if not content:
        # Modelos de "reasoning" às vezes devolvem o texto neste outro campo.
        content = getattr(message, "reasoning", None)

    print("[OK] Conexao com o OpenRouter funcionando.")
    print(f"Resposta do modelo: {content!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
