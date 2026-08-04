from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from openai import OpenAI

logger = logging.getLogger(__name__)

_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
if _ENV_PATH.exists():
    for _line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

_MODEL = "openai/gpt-oss-120b:free"
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 5.0

_SETOR_PARA_QDRANT: dict[str, str] = {
    "healthtech": "saude",
    "saúde": "saude",
    "saude": "saude",
    "fintech": "financas",
    "finanças": "financas",
    "financas": "financas",
    "insurtech": "financas",
    "agritech": "agro",
    "agronegócio": "agro",
    "agronegocio": "agro",
    "agro": "agro",
    "retailtech": "varejo",
    "varejo": "varejo",
    "automação industrial": "industria",
    "automacao industrial": "industria",
    "industria": "industria",
    "infraestrutura de ia": "geral",
    "dados e analytics": "geral",
}


def resolver_setor_qdrant(setor: str | None) -> list[str]:
    """Mapeia o setor do perfil para os valores usados como filtro no Qdrant."""
    if not setor:
        return ["geral"]
    chave = setor.strip().lower()
    setor_qdrant = _SETOR_PARA_QDRANT.get(chave)
    if setor_qdrant:
        return [setor_qdrant, "geral"]
    return ["geral"]


def _get_client() -> OpenAI:
    if not hasattr(_get_client, "_instance"):
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENROUTER_API_KEY não configurada no .env")
        _get_client._instance = OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )
    return _get_client._instance


def _chamar_llm(prompt: str) -> str | None:
    try:
        client = _get_client()
    except EnvironmentError as exc:
        logger.warning("OpenRouter indisponível: %s", exc)
        return None

    for tentativa in range(1, _MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            return (response.choices[0].message.content or "").strip() or None
        except Exception as exc:  # noqa: BLE001
            code = getattr(exc, "status_code", None)
            if code == 429 and tentativa < _MAX_RETRIES:
                delay = _RETRY_BASE_DELAY * (2 ** (tentativa - 1))
                logger.warning(
                    "Rate limit (429). Tentativa %d/%d — aguardando %.0fs.",
                    tentativa, _MAX_RETRIES, delay,
                )
                time.sleep(delay)
                continue
            logger.error(
                "Erro na API OpenRouter/query (tentativa %d/%d): %s",
                tentativa, _MAX_RETRIES, exc,
            )
            return None
    return None


def _construir_prompt(perfil: dict) -> str:
    setor = perfil.get("setor") or "não informado"
    produto = perfil.get("produto") or "não informado"
    ia_tipo = perfil.get("ia_tipo") or "não informado"
    uso_ia = perfil.get("uso_ia_descricao") or "não informado"
    maturidade = perfil.get("maturidade") or "não informado"
    ia_core = perfil.get("ia_core_product")

    if ia_core is True:
        foco_ia = "A IA é o core do produto (stack técnica é crítica)"
    elif ia_core is False:
        foco_ia = "A IA é suporte ao negócio (casos de uso aplicados importam mais)"
    else:
        foco_ia = "Papel da IA no produto não informado"

    return f"""Você é um especialista em tecnologias NVIDIA para startups de IA.

Você recebeu o perfil de uma startup e deve gerar uma query semântica que será usada para buscar em uma base de conhecimento sobre tecnologias NVIDIA.

## Perfil da startup
- Setor: {setor}
- Produto: {produto}
- Como a IA é usada: {uso_ia}
- Tipo de IA utilizado: {ia_tipo}
- Estágio de maturidade: {maturidade}
- Papel da IA: {foco_ia}

## Sua tarefa
Monte uma query semântica em linguagem natural que capture fielmente o que essa startup faz com IA e o que ela precisa para escalar ou melhorar isso.

## Regras
- A query deve ter entre 1 e 3 frases
- Escreva em português
- Baseie-se APENAS no que está descrito no perfil — NÃO invente casos de uso, tecnologias ou problemas que não estejam explicitamente mencionados
- Seja específico: mencione o domínio, o tipo real de tarefa de IA e a necessidade técnica derivada do perfil
- NÃO cite marcas ou produtos NVIDIA na query — ela será usada para busca semântica
- NÃO adicione texto explicativo ou introdução — responda APENAS com a query

## Exemplo de query bem formada
"startup de saúde com produto de visão computacional em estágio MVP buscando solução para inferência de modelos de imagem médica em produção"

Responda APENAS com a query, sem mais nenhum texto."""


def _query_fallback(perfil: dict) -> str:
    """Fallback determinístico caso o LLM não esteja disponível."""
    setor = perfil.get("setor") or ""
    uso_ia = perfil.get("uso_ia_descricao") or perfil.get("produto") or ""
    ia_tipo = perfil.get("ia_tipo") or ""
    maturidade = perfil.get("maturidade") or ""
    ia_core = perfil.get("ia_core_product")

    partes: list[str] = []
    if setor:
        partes.append(f"startup de {setor}")
    if uso_ia:
        partes.append(f"que {uso_ia}")
    if ia_tipo:
        partes.append(f"usando {ia_tipo}")
    if maturidade:
        partes.append(f"em estágio {maturidade}")

    if ia_core is True:
        partes.append("buscando stack técnica para acelerar e escalar modelos em produção")
    elif ia_core is False:
        partes.append("buscando soluções de IA aplicadas ao negócio")
    else:
        partes.append("buscando soluções de IA")

    return " ".join(partes) if partes else "startup buscando tecnologias NVIDIA"


def gerar_query(perfil: dict) -> str:
    """Analisa o perfil de uma startup e gera uma query semântica para o RAG.

    Usa LLM para raciocinar sobre os gaps de IA da empresa e formular uma
    query que maximiza a relevância dos chunks retornados pelo Qdrant.

    Args:
        perfil: dicionário com campos setor, produto, ia_tipo, maturidade,
                ia_core_product.

    Returns:
        Query semântica em linguagem natural, nunca vazia (usa fallback
        determinístico se o LLM não responder).
    """
    prompt = _construir_prompt(perfil)

    resposta = _chamar_llm(prompt)
    if resposta:
        logger.info("Query gerada: %s", resposta)
        return resposta

    logger.warning("LLM indisponível — usando query determinística")
    query = _query_fallback(perfil)
    logger.info("Query determinística: %s", query)
    return query


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)

    perfil_exemplo = {
        "setor": "Healthtech",
        "produto": "plataforma de diagnóstico por imagem",
        "ia_tipo": "Visão Computacional",
        "maturidade": "MVP",
        "ia_core_product": True,
    }

    print("Perfil:")
    print(json.dumps(perfil_exemplo, ensure_ascii=False, indent=2))
    print("\nQuery gerada:")
    print(gerar_query(perfil_exemplo))
