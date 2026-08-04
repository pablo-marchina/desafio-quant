---
name: langgraph-nvidia-startup-radar
description: Build or review LangGraph-based multiagent architecture for the NVIDIA Startup AI Radar project. Use when Codex needs to design, implement, refactor, test, or document the Search Planner, Scraper, Extractor, Classifier, Evidence Validator, NVIDIA RAG, Recommendation, and Briefing agents; define graph state, node contracts, edges, checkpoints, retries, human-in-the-loop gates, evidence traceability, or recommendation flows aligned with the project document.
---

# LangGraph NVIDIA Startup Radar

## Overview

Use this skill to keep LangGraph work aligned with the NVIDIA Startup AI Radar source-of-truth document and the project's agent boundaries. Prefer explicit state, typed schemas, traceable evidence, and conditional graph transitions over a linear prompt chain.

## Required Context

Before changing architecture or agent behavior, read:

- `AGENTS.md`
- `ai-agent-system/docs/Projeto_ NVIDIA Startup AI Radar (1).md`

Treat those files as the source of truth. Do not invent classification criteria, NVIDIA technologies, startup facts, or evidence.

## Workflow

1. Map the requested change to one or more agent responsibilities.
2. Read `references/radar-agent-contracts.md` when adding or changing state fields, outputs, validation rules, or recommendation payloads.
3. Read `references/langgraph-patterns.md` when building graph topology, conditional edges, retries, checkpoints, persistence, or human review gates.
4. Preserve module boundaries: do not mix scraping, RAG, classification, validation, and recommendation logic in one file.
5. Add or update tests around state transitions, evidence requirements, classifier decisions, and recommendation provenance when behavior changes.
6. Keep URLs, source labels, timestamps, snippets, and confidence metadata available through the pipeline.

## Implementation Rules

- Use LangGraph for stateful orchestration, not just a list of prompt calls.
- Model graph state with explicit typed schemas.
- Make every node accept the graph state and return only its state updates.
- Use conditional edges for missing evidence, low confidence, source conflicts, recommendation blocking, and human review.
- Block recommendations when validated evidence is insufficient.
- Keep NVIDIA RAG retrieval citation-aware: recommendations must point to both startup evidence and NVIDIA knowledge evidence.
- Store raw evidence separately from extracted claims and derived classifications.
- Prefer small modules under the existing `ai-agent-system` structure.

## Graph Shape

The default graph should follow this project flow:

`query -> search_planner -> scraper -> extractor -> validator -> classifier -> diagnostics -> nvidia_rag -> recommendation -> briefing`

Use loops when needed:

- Back to `scraper` when evidence is too thin.
- Back to `extractor` when content is present but claims are incomplete.
- To human review when claims conflict or a high-impact recommendation has weak support.
- To `nvidia_rag` again when recommendation needs more precise product evidence.

## References

- `references/radar-agent-contracts.md`: agent inputs, outputs, evidence rules, and recommendation payloads.
- `references/langgraph-patterns.md`: recommended LangGraph graph, routing, persistence, retry, and test patterns.
