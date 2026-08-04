from typing import Dict, List

import httpx

from .config import OPENROUTER_API_KEY, OPENROUTER_BASE, OPENROUTER_MODEL


def _heuristic_rerank(passages: List[Dict], top_k: int, reason: str) -> List[Dict]:
    ranked: List[Dict] = []
    for i, passage in enumerate(passages[:top_k]):
        item = dict(passage)
        item["score"] = 1.0 - (i * 0.01)
        item["rerank_provider"] = "heuristic"
        item["rerank_status"] = "fallback"
        item["rerank_reason"] = reason
        ranked.append(item)
    return ranked


def rerank_with_openrouter(query: str, passages: List[Dict], top_k: int = 5) -> List[Dict]:
    """
    Reordena trechos recuperados usando OpenRouter.
    Se a API nao estiver disponivel, retorna ranking heuristico com metadados
    explicitos para facilitar o debug da entrega.
    """
    if not OPENROUTER_API_KEY:
        return _heuristic_rerank(passages, top_k, "missing_openrouter_api_key")

    url = f"{OPENROUTER_BASE}/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}

    scored: List[Dict] = []
    had_request_error = False

    for passage in passages[: min(len(passages), 50)]:
        item = dict(passage)
        prompt = (
            f"Avalie a relevancia do seguinte trecho para a consulta:\n"
            f"Consulta: {query}\n"
            f"Trecho: {item.get('document') or item.get('text')[:500]}\n"
            "Responda apenas com um numero entre 0 e 100 representando a relevancia."
        )
        payload = {
            "model": OPENROUTER_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 16,
            "temperature": 0.0,
        }

        try:
            response = httpx.post(url, json=payload, headers=headers, timeout=20.0)
            response.raise_for_status()
            data = response.json()
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            score = 0.0
            for tok in text.split():
                try:
                    score = float(tok) / 100.0
                    break
                except Exception:
                    continue
            item["score"] = score
            item["rerank_provider"] = "openrouter"
            item["rerank_status"] = "ok"
            item["rerank_reason"] = None
        except Exception as exc:
            had_request_error = True
            item["score"] = 0.0
            item["rerank_provider"] = "openrouter"
            item["rerank_status"] = "error"
            item["rerank_reason"] = exc.__class__.__name__

        scored.append(item)

    if had_request_error and not any(item.get("rerank_status") == "ok" for item in scored):
        return _heuristic_rerank(passages, top_k, "openrouter_request_failed")

    scored.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    return scored[:top_k]
