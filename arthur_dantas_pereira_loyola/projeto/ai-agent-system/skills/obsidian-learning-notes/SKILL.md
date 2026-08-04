---
name: obsidian-learning-notes
description: Create and update learner-friendly Obsidian notes for the NVIDIA Startup AI Radar project. Use when documenting project progress, explaining code, maintaining learning MOCs, updating the handoff, translating technical changes into beginner explanations, or drawing LangGraph/pipeline flows with adjacent steps and return loops.
---

# Obsidian Learning Notes

Use this skill to keep the user's Obsidian vault useful as a study notebook, not just a change log.

## Vault Targets

- Vault: `C:\Users\Inteli\Desktop\Projeto Nvidia`
- Main project MOC: `MOC - NVIDIA Startup AI Radar.md`
- Learning MOC: `MOC - Aprendizados NVIDIA Startup AI Radar.md`
- Single living handoff: `Sessao 2026-06-14 - Handoff para Proximo Agente.md`

Keep only one handoff file current. Update that file in place instead of creating a new handoff per session.

## Note Style

For learning notes, include:

1. A plain-language explanation for a beginner.
2. A concrete analogy when helpful.
3. The relevant files and why each matters.
4. Key code snippets, kept short.
5. A flow view that shows neighboring steps in order.
6. Return loops when the pipeline can go backward or retry.
7. What changed, why it changed, and what to study next.

Use Obsidian links for concepts and files-as-concepts:

```markdown
[[LangGraph]]
[[Extractor Agent]]
[[Evidence Validator Agent]]
[[NVIDIA RAG Agent]]
```

## Flow Format

Prefer compact text diagrams for pipeline learning. Use adjacent nodes so the user can see the "esteira" step by step.

Basic flow:

```text
query
 -> search_planner
 -> scraper
 -> extractor
 -> validator
 -> classifier
 -> nvidia_rag
 -> recommendation
 -> briefing
```

Show loops explicitly:

```text
validator
 -> if evidence is enough: classifier
 -> if evidence is weak and attempts remain: scraper
 -> if evidence is still weak: briefing_limited
```

When documenting graph behavior, always include:

- the happy path;
- the weak-evidence path;
- the blocked recommendation path;
- the final output path.

## Code Explanation Pattern

When explaining code, use this structure:

```markdown
## Arquivo

`path/to/file.py`

## Para que serve

Short beginner explanation.

## Trecho importante

```python
small_snippet()
```

## Em linguagem simples

Explain what the snippet does.

## Por que isso importa no projeto

Tie the code to evidence, traceability, recommendations, or tests.
```

Keep snippets short. Do not paste whole files unless the user asks.

## Handoff Updates

After meaningful code, architecture, environment, or testing changes, update the single handoff with:

- current branch and latest commit;
- Python/venv status when relevant;
- tests run and result;
- new or changed files;
- current architecture summary;
- next recommended step;
- constraints: no APIs unless authorized, no secrets, use venv Python.

The handoff should remain copy-pasteable as a prompt for a new agent.

## Learning MOC Maintenance

When adding a learning note:

1. Add frontmatter with `tags` and `aliases`.
2. Link it from `MOC - Aprendizados NVIDIA Startup AI Radar.md`.
3. Avoid duplicate links in the MOC.
4. Prefer atomic notes: one note per concept or workflow.

## Project-Specific Emphasis

For this project, keep explaining:

- why `venv` matters;
- how schemas protect against API changes;
- how adapters normalize messy external data;
- how evidence moves from source document to claim to validation;
- why weak evidence blocks recommendations;
- how LangGraph differs from one linear prompt;
- how each commit changes the system.
