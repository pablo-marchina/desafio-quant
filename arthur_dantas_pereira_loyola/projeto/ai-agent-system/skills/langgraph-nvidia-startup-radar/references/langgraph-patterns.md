# LangGraph Patterns

Use this reference when implementing the orchestration layer for NVIDIA Startup AI Radar.

## Preferred Structure

Keep graph orchestration separate from business logic:

```text
agent/
  graph/
    state.py
    nodes.py
    edges.py
    builder.py
  search_planner/
  scraper/
  extractor/
  classifier/
  validator/
  rag/
  recommendation/
  briefing/
```

Each node should be a thin adapter:

```python
def classify_startup(state: RadarState) -> dict[str, Any]:
    result = classifier.classify(
        profile=state["extracted_startups"][0],
        claims=state["claims"],
        validation=state["validation"],
    )
    return {"classification": result}
```

## Routing Conditions

Use condition functions for important business decisions:

```python
def route_after_validation(state: RadarState) -> str:
    validation = state["validation"]
    if validation.requires_human_review:
        return "human_review"
    if not validation.has_minimum_evidence:
        return "scraper"
    return "classifier"
```

Recommended gates:

- Missing or thin evidence: collect more sources.
- Conflicting claims: human review or additional collection.
- Low classifier confidence: require review before recommendations.
- No validated AI usage: stop recommendation and generate a limited briefing.
- Weak NVIDIA product citation: retrieve more RAG context before final recommendation.

## Checkpoints And Recovery

Use checkpointing for long-running collection, extraction, RAG, and briefing runs. Persist enough state to resume after scraping failures or model errors without losing collected evidence.

Track:

- query and search plan
- source documents and retrieval metadata
- extraction outputs
- validation report
- current graph step
- retry count and recoverable errors

## Human In The Loop

Add human review points for:

- evidence conflicts
- high-value startups with weak public evidence
- ambiguous AI-Native versus AI-Enabled classification
- recommendations with high implementation complexity
- attempts to infer private technical stack from indirect signals

## Testing

Test the graph as behavior, not only as isolated functions:

- A startup with no AI evidence should not receive NVIDIA technology recommendations.
- A startup with only one weak source should loop to additional collection or review.
- A startup using LLM APIs in customer support should be eligible for NIM, NeMo Guardrails, Triton, and cost/latency benchmarking only when the evidence supports that use case.
- A data-intensive startup should receive RAPIDS/cuDF/cuML recommendations only when tabular or data pipeline evidence exists.
- Every final briefing should contain source IDs or URLs for claims and recommendations.
