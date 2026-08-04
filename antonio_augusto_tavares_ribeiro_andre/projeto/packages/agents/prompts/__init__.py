"""Prompts versionados dos nós LLM (F0.12).

Uso: `from packages.agents.prompts import get_prompt; p = get_prompt('extractor')`.
O `p.version_tag` vai p/ `traced_config(prompt_version=...)` (F0.8) e p/ `run` (F0.6).
"""

from .registry import PROMPT_NODES, ModelProfile, Prompt, all_prompts, get_prompt

__all__ = ["get_prompt", "all_prompts", "Prompt", "PROMPT_NODES", "ModelProfile"]
