# Priority Candidate Queue

GraphRAG and other retrieval improvements are P1 benchmark candidates, not automatic runtime additions.

| Order | Candidate | Required direct metrics |
|---:|---|---|
| 1 | Source-trust-aware reranking | source trust, context precision, unsupported claim rate |
| 2 | Counter-evidence retrieval | contradiction detection, unsupported claim rate, recommendation precision |
| 3 | Evidence graph construction / GraphRAG | multi-hop accuracy, graph lineage coverage, recommendation precision |
| 4 | Strong reranker benchmark | context precision, answer faithfulness, latency p95 |
| 5 | Parent-child / small-to-big retrieval | context recall, context precision, answer completeness |
| 6 | Agentic retrieval loop | evidence sufficiency, failure rate, latency p95 |
| 7 | RAG evaluation harness | faithfulness, answer relevancy, context recall, context precision |
| 8 | OpenTelemetry GenAI tracing | trace coverage, debug time, failure localization |
| 9 | LLM/RAG security suite | attack pass rate, leakage rate, tool misuse rate |
| 10 | Data contracts/schema validation | schema pass rate, invalid extraction rate |
