.PHONY: dev lint test

dev:
	uvicorn app.main:app --reload

lint:
	ruff check .

test:
	pytest
