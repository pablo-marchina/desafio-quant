# Python Environment

This project uses Python for the agent pipeline, API, scraping, extraction, RAG, and recommendation services.

## Official Python Version

Use Python 3.12 as the official project version. It is mature for FastAPI, LangGraph/LangChain, Playwright, Scrapy, PostgreSQL clients, Qdrant, and common RAG tooling.

Python 3.13 can be used temporarily for local development if Python 3.12 is not installed. Avoid Python 3.14 for now because AI and scraping libraries may lag behind the newest Python release.

## Existing Environment

If you already have a compatible virtual environment, keep using it. A virtual environment may exist at:

```powershell
.\venv
```

Activate it from the repository root:

```powershell
.\venv\Scripts\Activate.ps1
```

Check Python and pip:

```powershell
python --version
python -m pip --version
```

If the environment reports Python 3.14, recreate it after installing Python 3.12:

```powershell
Remove-Item -Recurse -Force .\venv
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

## Install Dependencies

From `ai-agent-system`:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m playwright install
```

Use `requirements.txt` for runtime dependencies and `requirements-dev.txt` for local development and tests.

## Environment Variables

Copy the example file:

```powershell
Copy-Item .env.example .env
```

Fill only local secrets in `.env`. Do not commit `.env`.

## Notes

- Keep `venv/` and `.venv/` out of Git.
- Prefer adding dependencies to `requirements.txt` before installing them manually.
- Keep NVIDIA recommendation logic evidence-driven, as required by the project document.
