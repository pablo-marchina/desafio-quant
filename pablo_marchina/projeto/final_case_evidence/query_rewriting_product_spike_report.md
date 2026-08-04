# Query Rewriting Product Spike Report

Generated at: `2026-07-01T05:58:27.637705+00:00`
Decision: `PROMOTE_TO_PRODUCT_SPIKE`
Baseline score: `0.575`
Candidate score: `1.0`
Quality delta: `0.425`

This report is a product spike benchmark. It does not promote query rewriting to default runtime behavior.

| Case | Baseline | Candidate | Delta | Candidate chunks |
|---|---:|---:|---:|---|
| business_vocab_to_triton | 0.15 | 1.0 | 0.85 | triton_inference, nim_endpoint, generic_ai |
| business_vocab_to_nim | 1.0 | 1.0 | 0.0 | nim_endpoint, triton_inference, generic_ai |
