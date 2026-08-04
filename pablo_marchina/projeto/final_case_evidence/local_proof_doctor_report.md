# Local Proof Doctor

Status: `PASS`
Effective route: `external_services`
Recommended route: Use already-running PostgreSQL and Qdrant via env vars, then run full proof.
Environment fix required: `False`
Can retry without code changes: `True`

Doctor passed via external_services. The full proof can be retried without code changes.

## Exact Commands

- `set PRODUCT_DB_URL=postgresql://postgres:postgres@localhost:5432/startup_radar`
- `set QDRANT_URL=http://localhost:6333`
- `set QDRANT_COLLECTION=nvidia_corpus`
- `python scripts/local_proof_doctor.py`
- `python scripts/prove_final_product.py --full --skip-live`

## Blocking Checks

- None
