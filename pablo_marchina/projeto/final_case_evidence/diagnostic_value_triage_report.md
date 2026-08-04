# Diagnostic Value Triage Report

Generated at: `2026-07-01T05:58:25.269986+00:00`
Baseline quality score: `0.5869`
Spike candidates: `6`

This report finds marginal system-value before implementing technologies. A `SPIKE_CANDIDATE` is not product adoption; it is permission to run the smallest real spike.

## Recommended Spikes

| Family | Affected-case delta | Global delta | Affected cases | Next step |
|---|---:|---:|---:|---|
| Counter-evidence retrieval and contradiction checks | 0.105 | 0.015 | 1 | Build the smallest disposable spike that targets the affected diagnostic cases, then run a real quality benchmark before product promotion. |
| GraphRAG / evidence graph expansion | 0.0991 | 0.0142 | 1 | Build the smallest disposable spike that targets the affected diagnostic cases, then run a real quality benchmark before product promotion. |
| Query rewriting and multi-query expansion | 0.0955 | 0.0136 | 1 | Build the smallest disposable spike that targets the affected diagnostic cases, then run a real quality benchmark before product promotion. |
| Recommendation specificity and next-best-action enrichment | 0.0937 | 0.0134 | 1 | Build the smallest disposable spike that targets the affected diagnostic cases, then run a real quality benchmark before product promotion. |

## Family Decisions

| Family | Decision | Baseline | Oracle | Affected-case delta | Global delta | Rationale |
|---|---|---:|---:|---:|---:|---|
| Counter-evidence retrieval and contradiction checks | SPIKE_CANDIDATE | 0.5869 | 0.6019 | 0.105 | 0.015 | Oracle lift shows measurable marginal system-value for this family. |
| GraphRAG / evidence graph expansion | SPIKE_CANDIDATE | 0.5869 | 0.601 | 0.0991 | 0.0142 | Oracle lift shows measurable marginal system-value for this family. |
| Query rewriting and multi-query expansion | SPIKE_CANDIDATE | 0.5869 | 0.6005 | 0.0955 | 0.0136 | Oracle lift shows measurable marginal system-value for this family. |
| Recommendation specificity and next-best-action enrichment | SPIKE_CANDIDATE | 0.5869 | 0.6003 | 0.0937 | 0.0134 | Oracle lift shows measurable marginal system-value for this family. |
| Evidence sufficiency and abstention gate | SPIKE_CANDIDATE | 0.5869 | 0.6134 | 0.0928 | 0.0265 | Oracle lift shows measurable marginal system-value for this family. |
| Source trust and freshness ranking | SPIKE_CANDIDATE | 0.5869 | 0.5983 | 0.0797 | 0.0114 | Oracle lift shows measurable marginal system-value for this family. |
| Cost, latency, and reliability controls | NO_MEASURED_HEADROOM | 0.5869 | 0.5904 | 0.0246 | 0.0035 | Oracle lift is below the minimum value delta; implementation is not justified yet. |

## Diagnostic Cases

| Case | Baseline | Improvement opportunity | Target families |
|---|---:|---|---|
| Different vocabulary hides the right NVIDIA evidence | 0.5868 | Improve retrieval robustness when the same need is phrased differently. | query_rewriting_multiquery |
| Multi-hop gap-to-product reasoning is underspecified | 0.5724 | Improve explainability of why one NVIDIA path wins over adjacent options. | graphrag_evidence_graph |
| Negative signals should change confidence | 0.5503 | Improve confidence calibration and evaluator trust when evidence conflicts. | counter_evidence_retrieval, evidence_sufficiency_abstention |
| Stale or weak sources compete with stronger evidence | 0.5897 | Improve trust by preferring stronger and fresher evidence without changing the claim. | source_trust_freshness_ranking |
| Recommendation should abstain when support is thin | 0.5213 | Improve trust by separating hypothesis from supported recommendation. | evidence_sufficiency_abstention |
| Next action is too generic to execute | 0.5805 | Improve actionability and evaluator confidence in the proposed next step. | recommendation_specificity_next_action |
| Same quality should become cheaper and more reliable | 0.7071 | Improve the product as a whole even when answer quality is already acceptable. | cost_latency_reliability_controls |
