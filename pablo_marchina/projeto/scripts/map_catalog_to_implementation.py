#!/usr/bin/env python3
"""Map every catalog entry to implementation status and batch-create missing modules."""

import csv
import importlib
import os
import re
import shutil
import socket
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

# ── Pre-cache codebase ────────────────────────────────────────────────
_codebase_text = ""
for p in ROOT.rglob("*.py"):
    sp = str(p)
    if "site-packages" in sp or ".venv" in sp or "__pycache__" in sp:
        continue
    try:
        _codebase_text += p.read_text(encoding="utf-8", errors="ignore") + "\n"
    except:
        pass


def codebase_refs(term: str) -> int:
    try:
        return len(re.findall(re.escape(term), _codebase_text, re.IGNORECASE))
    except:
        return 0


# ── Knowledge base: what's already implemented ────────────────────────

# Python packages already installed
INSTALLED_PACKAGES = {}
for pkg in [
    "fastapi",
    "sqlalchemy",
    "alembic",
    "pydantic",
    "pandas",
    "numpy",
    "scipy",
    "polars",
    "duckdb",
    "httpx",
    "networkx",
    "sentence_transformers",
    "langchain",
    "scrapy",
    "playwright",
    "docling",
    "unstructured",
    "pymupdf",
    "bs4",
    "instructor",
    "psutil",
    "rich",
    "click",
    "tqdm",
    "plotly",
    "jinja2",
    "requests",
    "lxml",
    "yaml",
    "uvicorn",
    "redis",
    "qdrant_client",
    "poetry",
    "sklearn",
    "opentelemetry",
    "dvc",
    "evidently",
    "ragas",
    "deepeval",
    "trulens",
    "wandb",
    "neptune",
    "pytesseract",
    "pdfplumber",
    "camelot",
    "markdown",
    "tabulate",
    "google.protobuf",
    "avro",
    "pyarrow",
    "msgpack",
    "rank_bm25",
    "splade",
    "colbert",
]:
    try:
        mod = importlib.import_module(pkg)
        ver = getattr(mod, "__version__", "ok")
        INSTALLED_PACKAGES[pkg] = ver
    except:
        pass

# Docker services that are running
DOCKER_RUNNING = {}
docker_ports = {
    "PostgreSQL": 5432,
    "Redis": 6379,
    "Qdrant": 6333,
    "Phoenix": 6006,
    "Prometheus": 9090,
    "MinIO": 9000,
    "Grafana": 3000,
    "Neo4j": 7474,
    "Weaviate": 8080,
}
for name, port in docker_ports.items():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1)
    try:
        s.connect(("localhost", port))
        DOCKER_RUNNING[name] = True
    except:
        DOCKER_RUNNING[name] = False
    finally:
        s.close()

# CLIs on PATH
CLI_AVAILABLE = {}
for name, cmd in [
    ("Git", "git"),
    ("Docker", "docker"),
    ("Python", "python"),
    ("Node.js", "node"),
    ("npm", "npm"),
    ("Docker Compose", "docker-compose"),
    ("Make", "make"),
    ("Trivy", "trivy"),
    ("Gitleaks", "gitleaks"),
    ("Tesseract", "tesseract"),
    ("TypeScript", "tsc"),
    ("Vite", "vite"),
]:
    CLI_AVAILABLE[name] = shutil.which(cmd) is not None

# APIs with keys configured
API_CONFIGURED = {}
api_keys = {
    "OpenAI API": "OPENAI_API_KEY",
    "NVIDIA AI API": "NVIDIA_API_KEY",
    "FireCrawl API": "FIRECRAWL_API_KEY",
    "LangSmith": "LANGCHAIN_API_KEY",
}
for name, env_var in api_keys.items():
    API_CONFIGURED[name] = os.environ.get(env_var, "") != ""

# Existing RAG modules
RAG_MODULES = {}
rag_dir = ROOT / "src" / "rag"
if rag_dir.exists():
    for f in rag_dir.glob("*.py"):
        RAG_MODULES[f.stem] = f

# ── Classify each catalog entry ───────────────────────────────────────


def classify(name: str, category: str) -> dict:
    entry = {"name": name, "category": category, "status": "unknown", "action": "", "detail": ""}

    canonical = name.strip().lower()

    # 1. Python package
    pkg_map = {
        "fastapi": "fastapi",
        "sqlalchemy": "sqlalchemy",
        "alembic": "alembic",
        "pydantic": "pydantic",
        "pandas": "pandas",
        "numpy": "numpy",
        "scipy": "scipy",
        "polars": "polars",
        "duckdb": "duckdb",
        "httpx": "httpx",
        "networkx": "networkx",
        "langchain": "langchain",
        "sentence-transformers": "sentence_transformers",
        "sentence transformers": "sentence_transformers",
        "scrapy": "scrapy",
        "playwright": "playwright",
        "docling": "docling",
        "unstructured": "unstructured",
        "pymupdf": "pymupdf",
        "beautifulsoup4": "bs4",
        "instructor": "instructor",
        "psutil": "psutil",
        "rich": "rich",
        "click": "click",
        "tqdm": "tqdm",
        "plotly": "plotly",
        "jinja2": "jinja2",
        "requests": "requests",
        "lxml": "lxml",
        "pyyaml": "yaml",
        "uvicorn": "uvicorn",
        "redis": "redis",
        "qdrant_client": "qdrant_client",
        "poetry": "poetry",
        "scikit-learn": "sklearn",
        "opentelemetry": "opentelemetry",
        "dvc": "dvc",
        "evidently": "evidently",
        "ragas": "ragas",
        "deepeval": "deepeval",
        "trulens": "trulens",
        "weights & biases": "wandb",
        "wandb": "wandb",
        "neptune": "neptune",
        "pytesseract": "pytesseract",
        "markdown": "markdown",
        "tabulate": "tabulate",
        "pdfplumber": "pdfplumber",
        "camelot": "camelot",
        "polars": "polars",
        "duckdb": "duckdb",
        "rank_bm25": "rank_bm25",
        "splade": "splade",
    }
    for key, pkg in pkg_map.items():
        if key in canonical:
            if pkg in INSTALLED_PACKAGES:
                entry["status"] = "installed"
                entry["detail"] = f"v{INSTALLED_PACKAGES[pkg]}"
            else:
                entry["status"] = "needs_install"
                entry["action"] = f"pip install {pkg}"
            break

    # 2. Docker service
    for dname in docker_ports:
        if dname.lower() in canonical:
            if DOCKER_RUNNING[dname]:
                entry["status"] = "running"
                entry["detail"] = f"port {docker_ports[dname]}"
            else:
                entry["status"] = "needs_docker"
                entry["action"] = f"docker compose up -d {dname.lower()}"
            break

    # 3. CLI
    for cli_name in CLI_AVAILABLE:
        if cli_name.lower() in canonical:
            if CLI_AVAILABLE[cli_name]:
                entry["status"] = "available"
            else:
                entry["status"] = "needs_install"
                entry["action"] = f"install {cli_name}"
            break

    # 4. API
    for api_name in API_CONFIGURED:
        if api_name.lower() in canonical.split("api")[0].strip() or canonical == api_name.lower():
            if API_CONFIGURED[api_name]:
                entry["status"] = "configured"
            else:
                entry["status"] = "needs_key"
                entry["action"] = "set API key in .env"
            break

    # 5. Data format
    data_formats = ["json", "yaml", "csv", "xml", "markdown", "parquet", "arrow", "protobuf", "avro"]
    if any(f in canonical for f in data_formats):
        entry["status"] = "builtin"
        entry["detail"] = "Python stdlib or installed"

    # 6. RAG module exists
    for mod_name in RAG_MODULES:
        mod_lower = mod_name.replace("_", " ").replace("-", " ")
        if mod_lower in canonical or canonical in mod_lower:
            entry["status"] = "implemented"
            entry["detail"] = f"src/rag/{mod_name}.py"
            break

    # 7. Codebase references
    refs = codebase_refs(name.split("/")[0].split("(")[0].strip()[:30])
    if refs > 0 and entry["status"] == "unknown":
        entry["status"] = "referenced"
        entry["detail"] = f"{refs} codebase refs"

    return entry


def main():
    csv_path = ROOT / "final_case_evidence" / "candidate_catalog.csv"
    with open(csv_path, newline="", encoding="utf-8") as f:
        catalog = list(csv.DictReader(f))

    results = []
    seen = set()
    for row in catalog:
        name = row["name"]
        cat = row["category"]
        if name in seen:
            continue
        seen.add(name)
        results.append(classify(name, cat))

    # Summary
    by_status = defaultdict(int)
    for r in results:
        by_status[r["status"]] += 1

    print(f"\n{'='*70}")
    print(f"  CATALOG IMPLEMENTATION STATUS — {len(results)} entries")
    print(f"{'='*70}")
    for s, c in sorted(by_status.items(), key=lambda x: -x[1]):
        pct = c / len(results) * 100
        print(f"  {s:20s}: {c:4d} ({pct:5.1f}%)")

    # Items needing code
    needs_code = [r for r in results if r["status"] == "unknown"]
    print(f"\n  Still unclassified ({len(needs_code)}):")
    for r in needs_code[:30]:
        print(f"    [{r['category'][:6]}] {r['name'][:50]}")

    # Save mapping
    out_path = ROOT / "final_case_evidence" / "catalog_implementation_map.json"
    import json

    out_path.write_text(
        json.dumps(
            {
                "total": len(results),
                "summary": dict(by_status),
                "entries": results,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"\nSaved: {out_path}")

    return results, by_status


if __name__ == "__main__":
    main()
