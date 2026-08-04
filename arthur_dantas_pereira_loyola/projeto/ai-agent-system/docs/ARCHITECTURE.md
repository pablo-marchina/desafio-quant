# NVIDIA Startup AI Radar Architecture

This document defines the initial architecture for deliverables 1 and 2:

- Deliverable 1: public startup scraping and evidence collection.
- Deliverable 2: LangGraph-based multiagent orchestration.

The source of truth remains `docs/Projeto_ NVIDIA Startup AI Radar (1).md`.

## Principles

- Preserve traceability from collection to briefing.
- Keep raw source documents, extracted claims, classifications, and recommendations separate.
- Do not recommend NVIDIA technologies when validated startup evidence is insufficient.
- Use LangGraph as a stateful workflow, not as a linear prompt chain.
- Keep scraping, extraction, classification, RAG, recommendation, and briefing in separate modules.

## Initial Graph

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

The first implementation uses deterministic placeholder agents so the pipeline can be tested before adding model calls and real crawling.

## Evidence Gate

After validation:

- If evidence is sufficient, continue to classification.
- If evidence is weak and retry budget remains, return to scraping.
- If evidence remains weak after retries, continue to a limited briefing and block recommendations.

## Scraping Strategy

The scraping layer should expose a common collector interface and add adapters incrementally:

| Adapter | Use |
|---|---|
| `trafilatura` | Main text extraction from articles, blogs, and public pages. |
| `BeautifulSoup` | Simple HTML parsing. |
| `Playwright` | Dynamic pages that depend on JavaScript. |
| `Scrapy` | Structured crawling at larger scale. |
| `Firecrawl` | Optional managed clean extraction for RAG-friendly content. |

The MVP should start with simple collectors and preserve enough metadata to swap or combine adapters later.

## Source Metadata

Every collected source document must keep:

- URL
- domain
- title
- source type
- retrieval timestamp
- collection method
- raw or cleaned text

## Agent Responsibilities

| Agent | Responsibility |
|---|---|
| Search Planner | Convert the user query into keywords, target source types, and a collection plan. |
| Scraper | Collect public source documents and preserve provenance. |
| Extractor | Convert source text into startup profiles and evidence claims. |
| Evidence Validator | Assess evidence sufficiency, source quality, conflicts, and caveats. |
| Startup Classifier | Classify only as `AI-Native`, `AI-Enabled`, or `Non-AI`. |
| NVIDIA RAG | Retrieve citation-aware NVIDIA knowledge chunks. |
| Recommendation | Map validated gaps to NVIDIA technologies with evidence IDs. |
| Briefing | Produce an executive summary, caveats, evidence, classification, and next actions. |

## Next Implementation Steps

1. Replace placeholder collectors with `trafilatura` and `BeautifulSoup` adapters.
2. Add persistence for source documents, claims, and graph runs.
3. Add real LLM-backed extraction and classification with structured outputs.
4. Add Qdrant or pgvector-backed NVIDIA knowledge retrieval.
5. Add API routes to start analyses and fetch run status.
