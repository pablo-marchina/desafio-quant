"""Guarda hermética da suíte: nenhum `.env` de dev pode ligar um caminho de rede num teste
que se diz *offline*.

Os testes unitários são offline/determinísticos por contrato — a CI roda sem flags e sem
chaves. Mas `Settings` lê do `.env` local, e o `.env` de dev do projeto liga os flags do
caminho ao vivo (`CLASSIFIER_USE_LLM`, `EMBEDDINGS_USE_NV`, `INDEX_USE_QDRANT`,
`SCRAPER_USE_NETWORK`, …) p/ os runs de coorte reais. Com isso, um teste que chama um
nó/agente **sem injetar adapter** vai à rede: passa na CI (sem flags) e falha — *flaky* (LLM
não-determinística) ou `ConnectionError` (rede instável) — na máquina do dev. Já mordeu em
escala (medido: ~50 falhas sob a `.env` live; `test_classifier`, RAG layer inteira, scraper).

`pytest_configure` roda **antes da coleta** (logo, antes de qualquer fixture, inclusive a
module-scoped do `test_ragas` que constrói o retriever): pina os flags de caminho-ao-vivo em
`false` no ambiente — a var de ambiente tem **precedência** sobre o `.env` no pydantic-settings,
e o pin via env **sobrevive** ao `get_settings.cache_clear()` que vários testes chamam (pinar
o atributo da instância, não — por isso env, não `setattr`).

Não desliga os testes de rede opt-in (gated por `TAPI_NETWORK_TESTS` / `skipif(api_key)`, que
dependem das chaves, não destes flags), nem trava toggles intencionais — um teste que liga um
flag via `monkeypatch.setenv` + `cache_clear` no próprio corpo sobrepõe este default
(last-write-wins; ex.: `GPU_BENCHMARK_USE_MATRIX`, que nem entra na lista). Tampouco resolve
falhas *ambientais* de serviço local de pé (Postgres/Qdrant rodando) — essas são ortogonais.
"""

from __future__ import annotations

import os

import pytest

from packages.config import get_settings

# Flags que, herdados de um `.env` de dev, fariam um teste "offline" fazer I/O ao vivo
# (LLM / embeddings / índice / rerank / scraper). `gpu_benchmark_use_matrix` fica de fora: é
# caminho local (matriz versionada, sem rede) e tem teste que o liga via env + cache_clear.
_LIVE_PATH_FLAGS_OFF = (
    "PLANNER_USE_LLM",
    "EXTRACTOR_USE_LLM",
    "CLASSIFIER_USE_LLM",
    "RECOMMENDER_USE_LLM",
    "BRIEFING_USE_LLM",
    "BRIEFING_USE_GUARDRAILS",
    "EMBEDDINGS_USE_NV",
    "INDEX_USE_QDRANT",
    "RERANKER_USE_NV",
    "SCRAPER_USE_NETWORK",
    "RAGAS_USE_LLM",
)


def pytest_configure(config: pytest.Config) -> None:
    """Crava a suíte offline antes da coleta: flags de caminho-ao-vivo off + cache limpo."""
    for var in _LIVE_PATH_FLAGS_OFF:
        os.environ[var] = "false"
    get_settings.cache_clear()
