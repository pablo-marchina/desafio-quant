# Golden Examples — End-to-End Pipeline Evaluation

This directory contains golden startup cases for the end-to-end pipeline
evaluation harness. Each JSON file defines a startup profile, evidence
list, and expected outputs.

## Files

| File | Case | Expected Motion |
|------|------|----------------|
| `startup_high_fit.json` | AI-native HealthTech, strong evidence | immediate_outreach / high_priority_outreach |
| `startup_weak_evidence.json` | E-commerce, no AI signals, no evidence | not_recommended |
| `startup_non_ai.json` | Consulting firm, non-AI | not_recommended |
| `startup_no_rag_context.json` | AI company with gaps, no RAG corpus | any valid motion |
| `startup_rag_supported.json` | AI company with gaps + RAG corpus | same with/without RAG |
| `startup_validate_manually.json` | Medium evidence, low confidence | lack_evidence_more_research |
| `startup_monitor_or_discard.json` | Low AI signals, little evidence | monitor_and_nurture / not_recommended |
| `expected_outputs.json` | Expected motion, gaps, scores per case | — |

## Usage

```python
from tests.evals.helpers import load_golden_case, assert_expected_motion

case = load_golden_case("examples/golden/startup_high_fit.json")
result = run_full_pipeline(case.profile, case.evidence_list)
assert_expected_motion(result, case.expected["motion_in"])
```
