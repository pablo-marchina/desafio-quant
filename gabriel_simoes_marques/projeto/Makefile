.PHONY: install scraping-install api front ingest neo4j-up neo4j-down run-api

install:
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt

scraping-install:
	.venv/bin/playwright install chromium

api:
	PYTHONPATH=. .venv/bin/uvicorn api.main:app --reload --port 8000

front:
	cd frontend && npm run dev

ingest:
	PYTHONPATH=. .venv/bin/python rag/ingestion.py

neo4j-up:
	docker compose up neo4j -d

neo4j-down:
	docker compose down neo4j

run-api: api
