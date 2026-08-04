# Radar Agent Contracts

Use this reference when designing schemas, state fields, node outputs, database models, or tests for the NVIDIA Startup AI Radar pipeline.

## Canonical Agent Responsibilities

- Search Planner: convert a user query into search terms, source priorities, target sectors, and a collection plan.
- Scraper: collect public pages and preserve source URL, retrieval timestamp, title, source type, and raw text or cleaned text.
- Extractor: convert unstructured text into structured startup fields and explicit claims.
- Evidence Validator: assess source quality, claim support, conflicts, freshness, and evidence sufficiency.
- Startup Classifier: classify only as `AI-Native`, `AI-Enabled`, or `Non-AI`, with justification and cited evidence.
- NVIDIA RAG: retrieve NVIDIA knowledge chunks with citations and product relevance.
- Recommendation: connect validated startup profile and gaps to NVIDIA technologies, with technical and business reasoning.
- Briefing: produce an executive summary with evidence, classification, gaps, recommendations, and suggested approach.

## Minimum Graph State

Keep state typed and explicit. A practical baseline:

```python
class RadarState(TypedDict, total=False):
    query: str
    search_plan: SearchPlan
    sources: list[SourceDocument]
    extracted_startups: list[StartupProfile]
    claims: list[EvidenceClaim]
    validation: EvidenceValidationReport
    classification: StartupClassification
    technical_gaps: list[TechnicalGap]
    nvidia_context: list[NvidiaKnowledgeChunk]
    recommendations: list[NvidiaRecommendation]
    briefing: ExecutiveBriefing
    errors: list[PipelineError]
    review_required: bool
```

## Evidence Rules

- Preserve URLs from the first collection step.
- Separate raw source documents, extracted claims, and derived conclusions.
- Attach evidence IDs to each classification, gap, and recommendation.
- Treat weak, missing, stale, paywalled, or conflicting evidence as validation signals, not as facts to smooth over.
- Do not recommend NVIDIA technologies when the startup profile has no validated evidence.

## Classification Rules

Use only the project categories:

- `AI-Native`: the product deeply depends on AI to deliver value, often with proprietary data, AI-driven workflows, agents, operational integration, or differentiation beyond generic APIs.
- `AI-Enabled`: AI supports the operation or product, but is not the core value engine.
- `Non-AI`: no relevant AI usage is evidenced.

Every classification must include:

- label
- confidence
- concise rationale
- supporting evidence IDs
- missing evidence or caveats

## Recommendation Payload

Every recommendation must include:

- NVIDIA technology or program
- target gap
- technical justification
- business justification
- priority
- implementation complexity
- suggested next action for NVIDIA
- startup evidence IDs
- NVIDIA knowledge evidence IDs

Use only technologies named in the project document unless a later source-of-truth update adds more.
