.PHONY: install api frontend web up down migrate ingest embed corpus-report corpus-drift benchmark-retrieval benchmark-semantic-cache evals eval-answers eval-listings eval-gate eval-promote verify

install:
	uv sync
	npm --prefix frontend ci

api:
	uv run uvicorn app.main:app --reload --port 8000

# The marketplace (fictional listings, real tools) on :5173, with hot reload. Its API calls go to
# the web server below, which adds the credentials: run both, and the API.
frontend:
	npm --prefix frontend run dev

# The marketplace's web server on :8080: the built frontend, and its calls to the API.
web:
	uv run uvicorn web.main:app --reload --port 8080

up:
	docker compose up --build

down:
	docker compose down

migrate:
	uv run alembic upgrade head

# Two commands, composed here rather than in code: app/ingestion/ builds the corpus and
# knows nothing about how it is searched.
ingest:
	uv run python -m app.ingestion
	uv run python -m app.generation.rag.embed

embed:
	uv run python -m app.generation.rag.embed

corpus-report:
	uv run python -m app.ingestion.report

corpus-drift:
	uv run python -m app.ingestion.drift

benchmark-retrieval:
	uv run python -m benchmarks.retrieval.run

benchmark-semantic-cache:
	uv run python -m benchmarks.semantic_cache.run

# The whole real-model evaluation of what ships, then the gate: the same steps as evals.yml. ~$1.10.
evals:
	uv run python -m evals.answers.run --variant baseline
	uv run python -m evals.listings.run --path both
	uv run python -m evals.gate check

eval-answers:
	uv run python -m evals.answers.run

eval-listings:
	uv run python -m evals.listings.run

eval-gate:
	uv run python -m evals.gate check

eval-promote:
	uv run python -m evals.gate promote

verify:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy
	uv run pytest
	npm --prefix frontend run verify
