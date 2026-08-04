"""Testes do demo executável (F7.7) — só o caminho OFFLINE (sem rede/credencial).

Carrega `scripts/demo.py` por caminho (não é pacote) e exercita o modo default: o grafo
roda ponta a ponta e o briefing determinista é montado a partir de um caso rotulado. O
modo `--real` (rede/LLM) não é exercitado aqui — fica fora do CI por design.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_DEMO_PATH = Path(__file__).resolve().parents[1] / "scripts" / "demo.py"


def _load_demo():
    spec = importlib.util.spec_from_file_location("tapi_demo", _DEMO_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_offline_demo_runs_and_prints_briefing(capsys) -> None:
    demo = _load_demo()
    assert demo.main([]) == 0
    out = capsys.readouterr().out
    assert "PIPELINE LANGGRAPH" in out          # (1) grafo offline
    assert "BRIEFING EXECUTIVO" in out           # (2) briefing completo
    assert "AIMI=" in out and "alvo_graduacao" in out
    assert "evidência dos dois lados" in out     # invariante F4.5 visível no demo


def test_list_cases_lists_eval_ids(capsys) -> None:
    demo = _load_demo()
    assert demo.main(["--list"]) == 0
    out = capsys.readouterr().out
    assert "eval set" in out
    assert out.count("eval-") >= 20  # o set rotulado (F1.12) tem ~24 casos


def test_unknown_case_exits(capsys) -> None:
    demo = _load_demo()
    with pytest.raises(SystemExit):
        demo.main(["--case", "nao-existe-999"])
