# Production Runbook — NVIDIA Startup AI Radar

This is the authoritative procedure to build, start, validate, operate, and stop the complete product stack.

## 1. What the release executes

`docker compose up` runs the implemented product design, not a reduced demo:

- PostgreSQL for product records, audit history, workflow queue, and LangGraph checkpoints;
- Alembic migrations before application startup;
- Qdrant with the governed NVIDIA corpus;
- idempotent corpus ingestion using real `BAAI/bge-m3` embeddings;
- NVIDIA Triton serving the `cross_encoder` reranker;
- FastAPI with liveness, readiness, migration, dependency, and request-context checks;
- a durable PostgreSQL-backed workflow worker;
- the React/Vite frontend served by Nginx;
- a trusted internal proxy boundary so the browser never receives the API secret.

The first build and first corpus ingestion download container images and the embedding/reranker models. Keep sufficient disk, RAM, and outbound network access available.

## 2. Requirements

- Docker Desktop with Docker Compose v2;
- Git;
- Windows PowerShell 7;
- outbound access to Docker Hub, NVIDIA NGC, Hugging Face, and the API providers enabled in `.env`;
- for a public deployment, TLS termination in front of port 3000 and firewall rules that keep PostgreSQL, Qdrant, Triton, and the direct API private.

The default reranker is CPU-compatible. An NVIDIA GPU can later be assigned to Triton through Compose device reservations without changing the API contract.

## 3. Clone and configure

```powershell
git clone https://github.com/pablo-marchina/academy-nvidia.git
cd academy-nvidia
git checkout main

# Creates .env from the template with cryptographically random proxy and DB secrets.
./scripts/initialize_release_env.ps1
```

Open `.env` and set at least:

```dotenv
NVIDIA_API_KEY=<your NVIDIA API key>
```

Configure optional governed collectors only when you will use them:

```dotenv
SERPAPI_API_KEY=
FIRECRAWL_API_KEY=
GITHUB_TOKEN=
```

Never commit `.env`. To deliberately regenerate it, run:

```powershell
./scripts/initialize_release_env.ps1 -Force
```

## 4. Build and start everything

```powershell
docker compose pull postgres qdrant
docker compose up --build -d
```

Observe bootstrap and service state:

```powershell
docker compose ps
docker compose logs -f migrate rag-bootstrap triton-reranker api workflow-worker frontend
```

`migrate`, `init-volumes`, and `rag-bootstrap` are one-shot services. A successful completed state is expected. API and worker start only after the database schema, Qdrant corpus, and Triton reranker are ready.

## 5. Validate the running release

### Public entry point and liveness

```powershell
docker compose ps
Invoke-RestMethod http://localhost:3000/health
Invoke-RestMethod http://localhost:3000/api/health/live
```

### Full readiness gate

```powershell
$ready = Invoke-RestMethod http://localhost:3000/api/health/ready
$ready | ConvertTo-Json -Depth 10
if (-not $ready.ready) { throw 'Product readiness gate failed' }
```

A valid release requires all of the following:

- PostgreSQL responds and its Alembic revision equals repository head;
- local NVIDIA corpus files pass integrity and freshness checks;
- Qdrant contains the expected collection, corpus version, payload, points, and embedding dimension;
- Triton reports the `cross_encoder` model ready;
- all mandatory capabilities pass the central product readiness gate.

Inspect details:

```powershell
Invoke-RestMethod http://localhost:3000/api/health/product | ConvertTo-Json -Depth 10
Invoke-RestMethod http://localhost:3000/api/health/dependencies | ConvertTo-Json -Depth 10
Invoke-RestMethod http://localhost:3000/api/workflows/langgraph-status
```

The direct backend port is intentionally protected. Application requests should use `http://localhost:3000/api/...`, not port 8080.

## 6. Execute the real product workflow

Create a startup with real, entity-specific evidence. Replace this example with the company being analyzed.

```powershell
$startupBody = @{
  name = 'Example AI Startup'
  website = 'https://example.com'
  country = 'Brazil'
  sector = 'Enterprise AI'
  description = 'Evidence-backed description of the company.'
  product_summary = 'The company deploys an LLM application in production.'
  status = 'active'
  tags = @('llm', 'enterprise-ai')
  evidence = @(
    @{
      claim = 'The company operates an LLM product.'
      source_url = 'https://example.com/product'
      source_type = 'official_site'
      quote_or_evidence = 'Replace this with a verifiable excerpt from the official product page.'
      confidence = 'high'
      metadata = @{}
    }
  )
} | ConvertTo-Json -Depth 10

$startup = Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:3000/api/startups `
  -ContentType 'application/json' `
  -Body $startupBody
```

Queue the single production workflow. The API returns HTTP 202 immediately; PostgreSQL persists the request and the worker executes LangGraph.

```powershell
$workflow = Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:3000/api/workflows/product-runs `
  -ContentType 'application/json' `
  -Body (@{ startup_id = $startup.id; use_rag = $true } | ConvertTo-Json)

$workflowId = $workflow.id
```

Poll persisted state:

```powershell
do {
  Start-Sleep -Seconds 2
  $workflow = Invoke-RestMethod "http://localhost:3000/api/workflows/product-runs/$workflowId"
  Write-Host "$($workflow.status) — $($workflow.current_node)"
} while ($workflow.status -in @('queued', 'running'))

$workflow | ConvertTo-Json -Depth 20
if ($workflow.status -notin @('completed', 'degraded', 'awaiting_review')) {
  throw "Workflow ended with status $($workflow.status): $($workflow.error_message)"
}
```

Inspect node-level execution:

```powershell
Invoke-RestMethod "http://localhost:3000/api/workflows/product-runs/$workflowId/nodes" |
  ConvertTo-Json -Depth 10
```

When a run enters `awaiting_review`, retrieve the review payload and use the existing review/resume endpoints. The PostgreSQL LangGraph checkpointer preserves the interrupt state across API or worker restarts.

## 7. Use the dashboard

Open:

```text
http://localhost:3000
```

Keep the default incremental batch at five companies and the source budget at five. The dashboard can display more rows without forcing all of them through one blocking analysis request.

## 8. Validate before tagging a release

```powershell
python -m pip install -e '.[dev,full,observability,security]'
ruff check src tests scripts
pytest -q
pip-audit --strict
bandit -q -r src scripts -lll

Push-Location frontend
npm ci
npm audit --audit-level=high
npm run build
Pop-Location

python scripts/audit_nvidia_corpus_freshness.py --fail-on-stale --fail-on-expired
docker compose config --quiet
docker compose build api frontend triton-reranker
```

Then repeat the readiness and real-workflow validation from sections 5 and 6. A green unit suite alone is not a production acceptance result.

## 9. Refresh or re-ingest the NVIDIA corpus

Verify official sources and safely update only freshness metadata:

```powershell
python scripts/refresh_nvidia_corpus_metadata.py `
  --report-path data/product/corpus-refresh-report.json
python scripts/audit_nvidia_corpus_freshness.py --fail-on-stale --fail-on-expired
```

After changing curated corpus content or `sources.yaml`, rebuild Qdrant with real embeddings:

```powershell
docker compose run --rm rag-bootstrap python scripts/ingest_nvidia_corpus.py `
  --recreate-collection `
  --require-real-embeddings `
  --fail-on-validation-error
docker compose restart api workflow-worker
```

Confirm `/api/health/ready` again before accepting new work.

## 10. Operations

```powershell
# Follow application execution
docker compose logs -f api workflow-worker

# Restart stateless services
docker compose restart api workflow-worker frontend

# Apply a new repository revision
docker compose build api frontend triton-reranker
docker compose run --rm migrate
docker compose up -d

# Stop without deleting data
docker compose down

# Destructive reset: deletes PostgreSQL, Qdrant, model, and product volumes
docker compose down -v
```

Back up `postgres_data`, `qdrant_data`, and `product_data` before upgrades. Do not use `down -v` in production unless a full reset is intentional.

## 11. Release acceptance criteria

A release is accepted only when:

1. CI, offline evaluation, security audit, migration verification, frontend build, and Docker release validation are green;
2. required long-running containers are healthy and one-shot bootstrap services completed successfully;
3. `/api/health/ready` returns HTTP 200 with `ready=true`;
4. a real company can be created, queued, claimed by the worker, processed, and retrieved from persisted state;
5. every recommendation has company-specific evidence and citation-ready NVIDIA context;
6. no company exceeds the bounded recommendation/technology limits;
7. unsupported workload families and shared-directory contamination are absent;
8. dossier, brief, claims, gaps, scores, mappings, readiness records, and audit history are persisted and visible;
9. restarting API and worker does not lose queued or checkpointed workflow state;
10. the public deployment uses TLS, backups, secret rotation, monitoring, and network isolation.
