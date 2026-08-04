"""Validação do failover Cohere KEY_1 → KEY_2 → RRF — Fase 3 (RAG Agent).

Caso 1: KEY_1 responde com sucesso.
Caso 2: KEY_1 falha (429), KEY_2 responde com sucesso (rotação de chave).
Caso 3: KEY_1 e KEY_2 falham (401) — fallback para top-k do RRF.
Caso 4: nenhuma chave configurada — fallback para RRF sem chamar o SDK.

Roda isolado, sem precisar de Postgres/Qdrant nem de chamadas reais à API Cohere
(o cliente `cohere.AsyncClientV2` é mockado).

Uso:
    python tests/validate_phase3_rag.py
"""
from __future__ import annotations

import asyncio
import dataclasses
import logging
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents import rag_agent
from src.config import get_settings


_CHUNKS = [
    {"tech_name": "Triton", "category": "Inferência", "source_url": "https://x", "text": "texto sobre triton"},
    {"tech_name": "NeMo", "category": "LLM", "source_url": "https://y", "text": "texto sobre nemo"},
    {"tech_name": "RAPIDS", "category": "Dados", "source_url": "https://z", "text": "texto sobre rapids"},
]


class _LogCapture(logging.Handler):
    """Captura records de loggers específicos via handler injetado."""

    def __init__(self, *logger_names: str) -> None:
        super().__init__(level=logging.DEBUG)
        self._names = logger_names
        self.records: list[logging.LogRecord] = []
        for name in logger_names:
            log = logging.getLogger(name)
            log.addHandler(self)
            log.setLevel(logging.DEBUG)

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)

    def messages(self, level: int | None = None) -> list[str]:
        return [r.getMessage() for r in self.records if level is None or r.levelno >= level]

    def warnings(self) -> list[str]:
        return self.messages(logging.WARNING)

    def infos(self) -> list[str]:
        return self.messages(logging.INFO)

    def errors(self) -> list[str]:
        return self.messages(logging.ERROR)

    def __enter__(self) -> "_LogCapture":
        return self

    def __exit__(self, *_: object) -> None:
        for name in self._names:
            logging.getLogger(name).removeHandler(self)


def _fake_rerank_response(n: int) -> SimpleNamespace:
    results = [SimpleNamespace(index=i, relevance_score=1.0 - i * 0.1) for i in range(n)]
    return SimpleNamespace(results=results)


def _settings_with_keys(key1: str | None, key2: str | None):
    return dataclasses.replace(get_settings(), cohere_api_key_1=key1, cohere_api_key_2=key2)


async def _run_case(name: str, key1: str | None, key2: str | None, rerank_side_effect) -> dict:
    print(f"\n=== {name} ===")
    settings = _settings_with_keys(key1, key2)
    with patch("src.agents.rag_agent.get_settings", return_value=settings), \
         patch("cohere.AsyncClientV2") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.rerank = AsyncMock(side_effect=rerank_side_effect)
        with _LogCapture("agents.rag") as cap:
            results, rerank_ms = await rag_agent.rerank_with_cohere("query de teste", _CHUNKS, top_k=2)

    rotations = [m for m in cap.warnings() if "Rotacao de chave" in m]
    failures = [m for m in cap.warnings() if "Falha em Cohere" in m]
    all_failed = [m for m in cap.errors() if "Todas as chaves Cohere falharam" in m]
    no_key = [m for m in cap.warnings() if "Nenhuma COHERE_API_KEY" in m]
    successes = [m for m in cap.infos() if "Reranking de" in m]

    used_rrf_fallback = rerank_ms is None
    scores = [c.rerank_score for c in results]

    print(f"  rerank_ms={rerank_ms} | rotacoes={len(rotations)} | falhas={len(failures)} | scores={scores}")
    return {
        "results": results,
        "rerank_ms": rerank_ms,
        "rotations": rotations,
        "failures": failures,
        "all_failed": all_failed,
        "no_key": no_key,
        "successes": successes,
        "used_rrf_fallback": used_rrf_fallback,
    }


async def case1_key1_ok() -> None:
    out = await _run_case(
        "Caso 1: KEY_1 responde com sucesso",
        "fake-key-1", "fake-key-2",
        rerank_side_effect=[_fake_rerank_response(2)],
    )
    assert not out["used_rrf_fallback"], "esperava rerank_ms setado (sucesso na KEY_1)"
    assert not out["rotations"], "nao deveria rotacionar quando KEY_1 funciona de primeira"
    assert any("Cohere KEY_1" in m for m in out["successes"]), "esperava log de sucesso citando KEY_1"
    print("  ✅ OK")


async def case2_key1_fails_key2_ok() -> None:
    out = await _run_case(
        "Caso 2: KEY_1 falha (429), KEY_2 responde com sucesso",
        "fake-key-1", "fake-key-2",
        rerank_side_effect=[Exception("429 Too Many Requests"), _fake_rerank_response(2)],
    )
    assert not out["used_rrf_fallback"], "esperava rerank_ms setado (sucesso na KEY_2)"
    assert len(out["rotations"]) == 1, f"esperava 1 rotacao, obteve {out['rotations']}"
    assert "Cohere KEY_1 → Cohere KEY_2" in out["rotations"][0]
    assert len(out["failures"]) == 1 and "quota/rate-limit" in out["failures"][0]
    assert any("Cohere KEY_2" in m for m in out["successes"]), "esperava log de sucesso citando KEY_2"
    print("  ✅ OK")


async def case3_both_fail() -> None:
    out = await _run_case(
        "Caso 3: KEY_1 e KEY_2 falham — fallback RRF",
        "fake-key-1", "fake-key-2",
        rerank_side_effect=Exception("401 Unauthorized"),
    )
    assert out["used_rrf_fallback"], "esperava rerank_ms=None (fallback RRF)"
    assert all(c.rerank_score == 1.0 for c in out["results"])
    assert len(out["failures"]) == 2, f"esperava 2 falhas (KEY_1 e KEY_2), obteve {out['failures']}"
    assert out["all_failed"], "esperava log de erro 'Todas as chaves Cohere falharam'"
    print("  ✅ OK")


async def case4_no_keys() -> None:
    out = await _run_case(
        "Caso 4: nenhuma chave configurada — fallback RRF sem chamar o SDK",
        None, None,
        rerank_side_effect=Exception("nao deveria ser chamado"),
    )
    assert out["used_rrf_fallback"], "esperava rerank_ms=None (fallback RRF)"
    assert all(c.rerank_score == 1.0 for c in out["results"])
    assert out["no_key"], "esperava log 'Nenhuma COHERE_API_KEY configurada'"
    print("  ✅ OK")


async def main() -> None:
    await case1_key1_ok()
    await case2_key1_fails_key2_ok()
    await case3_both_fail()
    await case4_no_keys()
    print("\nTodos os casos passaram.")


if __name__ == "__main__":
    asyncio.run(main())
