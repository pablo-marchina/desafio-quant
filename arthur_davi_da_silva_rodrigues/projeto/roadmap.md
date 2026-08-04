# NVIDIA Startup AI Radar Roadmap

## Goal

Build an end-to-end system that discovers Brazilian AI startups, collects public evidence, classifies AI-native maturity, recommends NVIDIA technologies, and generates executive briefings for NVIDIA startup outreach.

## How The Project Will Work

The user starts with either a search query or a startup URL. The system runs a LangGraph workflow that searches public sources, scrapes pages, extracts structured facts, validates evidence, classifies the startup, retrieves NVIDIA knowledge through RAG, generates recommendations, and produces a briefing.

The first version should optimize for a complete vertical slice, not scale. A small but reliable pipeline that analyzes a few startups with citations is more valuable than a broad crawler with weak evidence.

## Phase 0: Project Foundation

Objective: create the base project structure and development workflow.

Tasks:

- Choose the app stack: recommended FastAPI backend, LangGraph agents, PostgreSQL, Qdrant, and a React/Next.js or simple Streamlit frontend for MVP.
- Create repository structure for `app/`, `web/`, `docs/`, `scripts/`, and `tests/`.
- Add environment configuration for API keys, database URLs, model provider, and scraper settings.
- Add Docker Compose for PostgreSQL and Qdrant.
- Add formatting, linting, and test commands.
- Create the initial database schema.

Done when:

- The backend starts locally.
- PostgreSQL and Qdrant run locally.
- A health check endpoint works.
- The project has repeatable setup instructions.

## Phase 1: NVIDIA Knowledge Base

Objective: build the RAG foundation before recommendations.

Tasks:

- Define the NVIDIA technology catalog.
- Ingest official NVIDIA pages and support materials listed in `tapi.md`.
- Store document metadata: title, URL, source type, product area, retrieved date.
- Clean text and split into semantic chunks.
- Generate embeddings and store them in Qdrant.
- Add BM25 lexical search.
- Add reranking.
- Build a citation-aware retrieval endpoint.

Done when:

- A user can ask "what NVIDIA products help with LLM inference latency?" and receive cited retrieved chunks.
- The system can return ranked technologies with source URLs.

## Phase 2: Startup Scraping Pipeline

Objective: collect public startup information with traceability.

Tasks:

- Implement URL-based scraping for official websites.
- Implement search-based discovery using search queries and source priorities.
- Add collectors for static pages with trafilatura or BeautifulSoup.
- Add Playwright support for JavaScript-heavy pages.
- Store raw source documents and cleaned text.
- Track scrape status, errors, and timestamps.
- Add source type labels: official site, blog, careers, news, directory, founder profile.

Done when:

- Given a startup URL, the system collects pages and stores source documents.
- Given a query, the system returns candidate startup sources.
- Each collected source has a URL, title, content, and status.

## Phase 3: Extraction and Evidence Model

Objective: convert scraped pages into structured, source-backed startup profiles.

Tasks:

- Define schemas for startup, founder, product, funding, customer, technology signal, and evidence claim.
- Build an extractor agent that outputs structured JSON.
- Store claims separately from final accepted facts.
- Link every claim to source document IDs.
- Add confidence scores and extraction timestamps.
- Add duplicate detection for repeated pages and repeated claims.

Done when:

- A scraped startup can produce a structured profile.
- Each important fact has evidence.
- Unsupported facts are marked as low confidence or requiring review.

## Phase 4: AI-Native Classification

Objective: classify startup maturity and explain why.

Tasks:

- Define AI-native, AI-enabled, and non-AI criteria.
- Create scoring dimensions:
  - AI workflow depth.
  - Proprietary data advantage.
  - Model customization.
  - Evaluation maturity.
  - Production deployment maturity.
  - Automation depth.
  - Governance readiness.
  - Vendor dependency risk.
- Build the Startup Classifier Agent.
- Build the Evidence Validator Agent.
- Add classification confidence and explanation.
- Add human review fields for corrections.

Done when:

- A startup profile receives a classification with scores and evidence.
- The UI or API can show why the label was assigned.

## Phase 5: Gap Diagnosis

Objective: identify technical and business gaps that NVIDIA can help solve.

Tasks:

- Define gap taxonomy:
  - External API dependency.
  - Inference latency.
  - Inference cost.
  - Model serving maturity.
  - Agent governance.
  - Data pipeline scale.
  - Voice AI maturity.
  - Healthcare compliance and production readiness.
  - Robotics or simulation needs.
  - Cybersecurity AI needs.
- Build the diagnostic agent.
- Connect gaps to evidence and startup context.
- Add priority and confidence for each gap.

Done when:

- The system can say what is missing or risky in a startup's AI stack.
- Each gap is tied to evidence or clearly marked as inference.

## Phase 6: Recommendation Engine

Objective: recommend NVIDIA technologies using startup gaps and RAG evidence.

Tasks:

- Build mapping rules from gap taxonomy to NVIDIA products.
- Combine rule-based matching with RAG retrieval.
- Add recommendation priority and implementation complexity.
- Generate technical and business justifications.
- Include next action for NVIDIA:
  - Invite to NVIDIA Inception.
  - Offer technical workshop.
  - Propose inference benchmark.
  - Share NIM or Triton resources.
  - Discuss GPU/data pipeline optimization.
  - Route to sector-specific solution discussion.
- Link recommendations to startup evidence and NVIDIA source chunks.

Done when:

- A startup receives a ranked recommendation list.
- Each recommendation includes what to do next and why it matters.

## Phase 7: Briefing Generator

Objective: create the final executive report.

Tasks:

- Define briefing template:
  - Executive summary.
  - Startup profile.
  - AI-native maturity.
  - Evidence summary.
  - AI stack gaps.
  - Recommended NVIDIA technologies.
  - Outreach angle.
  - Next action.
  - Sources.
- Build the Briefing Agent.
- Support Markdown export first.
- Add PDF export later if needed.
- Clearly separate sourced claims from model inference.

Done when:

- A user can generate a briefing from a completed startup analysis.
- The briefing is usable for outreach or internal qualification.

## Phase 8: Web Interface

Objective: make the system usable by a non-engineering operator.

Tasks:

- Build the first screen as the actual working search/analyze interface.
- Add discovery run status.
- Add startup list and filters.
- Add startup detail page.
- Add evidence viewer.
- Add maturity score panel.
- Add recommendation cards.
- Add briefing preview and export.
- Add manual correction controls for extracted facts.

Done when:

- A user can run the full workflow from the browser.
- A user can inspect evidence before trusting a recommendation.

## Phase 9: Differentiator

Objective: add a unique feature that makes the project stand out.

Recommended differentiator: AI-native threat and opportunity radar.

Tasks:

- Score each startup on wrapper risk versus AI-native defensibility.
- Compare the startup against likely moves from large AI labs.
- Identify where NVIDIA can help the startup become more defensible:
  - Own data moat.
  - Lower inference cost.
  - Better latency.
  - On-prem or private deployment.
  - Evaluation and guardrails.
  - Domain-specific acceleration.
- Display a radar view with risk, opportunity, NVIDIA fit, and urgency.

Done when:

- The system provides insight beyond a generic recommendation list.
- The output helps NVIDIA prioritize which startups deserve outreach first.

## Suggested MVP Scope

The MVP should include:

- URL-based startup analysis.
- Public website scraping.
- Structured extraction.
- Evidence validation.
- AI-native classification.
- NVIDIA RAG over a small curated knowledge base.
- Rule-assisted recommendation engine.
- Markdown briefing export.
- Minimal web interface or API-first demo.

Defer until after MVP:

- Large-scale crawling.
- Complex dashboards.
- PDF export.
- Automated email outreach.
- Multi-user permissions.
- Advanced analytics across hundreds of startups.

## Milestone Plan

### Week 1: Foundation and RAG

- Create project structure.
- Set up FastAPI, PostgreSQL, Qdrant, and LangGraph.
- Ingest a small NVIDIA knowledge base.
- Build retrieval with citations.

### Week 2: Scraping and Extraction

- Build startup URL analysis.
- Store source documents.
- Extract structured facts.
- Implement evidence claims.

### Week 3: Classification and Recommendations

- Build AI-native classifier.
- Build gap diagnostic logic.
- Build first recommendation mappings.
- Connect recommendations to NVIDIA RAG.

### Week 4: Briefing and Interface

- Generate Markdown briefings.
- Build the web workflow.
- Add evidence inspection.
- Polish demo data and project documentation.

## Testing Strategy

Core tests:

- Unit tests for schema validation.
- Unit tests for recommendation mappings.
- Integration tests for the startup analysis workflow.
- Retrieval tests for NVIDIA RAG citations.
- Snapshot tests for briefing output.

Evaluation checks:

- Are startup claims source-backed?
- Are classifications consistent with the rubric?
- Are recommendations traceable to both startup evidence and NVIDIA sources?
- Does the briefing avoid unsupported claims?

## Risks and Mitigations

Risk: scraping pages may fail or be blocked.

Mitigation: start with URL-based analysis, preserve scrape errors, and support manual source input.

Risk: LLM extraction may hallucinate facts.

Mitigation: store claims separately, require source links, and validate evidence before writing final facts.

Risk: recommendations may be generic.

Mitigation: require a gap taxonomy and NVIDIA source citations for every recommendation.

Risk: the project becomes too broad.

Mitigation: build one complete vertical slice first, then expand to more sources and sectors.

## Final Deliverables

- Scraping pipeline.
- LangGraph multi-agent workflow.
- NVIDIA RAG with reranking and citations.
- Recommendation engine.
- Web interface.
- Differentiator: AI-native threat and opportunity radar.
- Architecture docs, roadmap, glossary, and ADRs.
