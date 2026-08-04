"""Testes do registro de prompts versionados (F0.12).

Garantem que os 5 nós têm prompt carregável, com metadados coerentes com a
ARQUITETURA (search_planner→Nano/reasoning off; demais→Super/reasoning on;
recommender/briefing em PT-BR), que o `version_tag` é estável e flui para o
`traced_config` (carimbo no trace, F0.8) — fechando a cadeia da DoD.
"""

from __future__ import annotations

import pytest

from packages.agents.prompts import PROMPT_NODES, all_prompts, get_prompt
from packages.observability import traced_config

OUTPUT_FACING = {"recommender", "briefing"}  # F0.13: saída PT-BR


def test_all_nodes_load() -> None:
    prompts = all_prompts()
    assert set(prompts) == set(PROMPT_NODES)
    for p in prompts.values():
        assert p.template.strip()  # corpo não-vazio
        assert p.version  # versão declarada


def test_version_tag_format() -> None:
    p = get_prompt("extractor")
    assert p.version_tag == f"extractor@{p.version}"


@pytest.mark.parametrize("node", PROMPT_NODES)
def test_model_and_reasoning_match_architecture(node: str) -> None:
    p = get_prompt(node)
    if node == "search_planner":
        assert p.model == "fast" and p.reasoning is False
    else:
        assert p.model == "reason" and p.reasoning is True


@pytest.mark.parametrize("node", sorted(OUTPUT_FACING))
def test_output_facing_nodes_are_ptbr(node: str) -> None:
    assert get_prompt(node).output_lang == "pt-BR"


def test_content_sha_is_stable_hex12() -> None:
    sha = get_prompt("classifier").content_sha
    assert len(sha) == 12
    int(sha, 16)  # é hex
    assert get_prompt("classifier").content_sha == sha  # determinístico


def test_unknown_node_raises() -> None:
    with pytest.raises(KeyError):
        get_prompt("nao_existe")


def test_get_prompt_is_cached() -> None:
    assert get_prompt("briefing") is get_prompt("briefing")


def test_version_flows_into_trace_config() -> None:
    # A ponta da DoD: o version_tag do prompt vira prompt_version no RunnableConfig.
    p = get_prompt("recommender")
    cfg = traced_config(node=p.node, prompt_version=p.version_tag)
    assert cfg["metadata"]["prompt_version"] == "recommender@v1"
    assert cfg["run_name"] == "recommender"
