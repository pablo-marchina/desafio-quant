"""Registro de prompts versionados dos nós LLM (F0.12).

Cada nó do grafo (F2/F4) tem **um arquivo** aqui (`<node>.md`) com frontmatter
(`version`, `model`, `reasoning`, `output_lang`) + corpo = system prompt estável.
O `version_tag` (`<node>@<version>`) é carimbado no trace Langfuse (F0.8, via
`traced_config(prompt_version=...)`) e na tabela `run` (F0.6) — assim o eval (F7) sabe
contra qual versão de prompt mediu e o cache (F2.14) invalida quando a versão muda.

Os arquivos guardam só a instrução estável (system). O turno do usuário (conteúdo
dinâmico do `GraphState`) é montado pelos nós em F2 — por isso os prompts não têm
placeholders de runtime; os campos esperados ficam documentados em `inputs`.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml

ModelProfile = Literal["fast", "reason"]

_PROMPTS_DIR = Path(__file__).parent

# Nós com prompt versionado, na ordem do pipeline (ARQUITETURA §3).
# search_planner roda no Nano (fast); os demais no Super (reason, reasoning ON).
PROMPT_NODES: tuple[str, ...] = (
    "search_planner",
    "extractor",
    "classifier",
    "recommender",
    "briefing",
)


@dataclass(frozen=True)
class Prompt:
    """System prompt versionado de um nó + metadados de execução."""

    node: str
    version: str
    model: ModelProfile
    reasoning: bool
    output_lang: str
    template: str
    inputs: tuple[str, ...] = ()

    @property
    def version_tag(self) -> str:
        """Rótulo carimbado no trace/`run` (ex.: 'extractor@v1')."""
        return f"{self.node}@{self.version}"

    @property
    def content_sha(self) -> str:
        """Hash curto do corpo — detecta drift e compõe a chave de cache (F2.14)."""
        return hashlib.sha256(self.template.encode("utf-8")).hexdigest()[:12]


def _parse(path: Path) -> Prompt:
    raw = path.read_text(encoding="utf-8")
    if not raw.lstrip().startswith("---"):
        raise ValueError(f"Prompt {path.name} sem frontmatter delimitado por '---'.")
    _, frontmatter, body = raw.split("---", 2)
    meta = yaml.safe_load(frontmatter) or {}

    node = meta.get("node")
    if node != path.stem:
        raise ValueError(f"{path.name}: frontmatter node={node!r} != nome do arquivo {path.stem!r}")
    model = meta.get("model")
    if model not in ("fast", "reason"):
        raise ValueError(f"{path.name}: model deve ser 'fast'|'reason' (veio {model!r}).")
    body = body.strip()
    if not body:
        raise ValueError(f"{path.name}: corpo (system prompt) vazio.")

    return Prompt(
        node=node,
        version=str(meta["version"]),
        model=model,
        reasoning=bool(meta.get("reasoning", False)),
        output_lang=str(meta.get("output_lang", "pt-BR")),
        template=body,
        inputs=tuple(meta.get("inputs", [])),
    )


@lru_cache
def get_prompt(node: str) -> Prompt:
    """Carrega (cacheado) o prompt versionado de um nó."""
    if node not in PROMPT_NODES:
        raise KeyError(f"nó desconhecido: {node!r}; conhecidos: {PROMPT_NODES}")
    return _parse(_PROMPTS_DIR / f"{node}.md")


def all_prompts() -> dict[str, Prompt]:
    """Todos os prompts por nó (inventário p/ eval/diagnóstico)."""
    return {node: get_prompt(node) for node in PROMPT_NODES}
