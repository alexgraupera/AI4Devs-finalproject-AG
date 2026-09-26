.PHONY: install api ui up down migrate ingest embed corpus-report corpus-drift benchmark-retrieval benchmark-semantic-cache eval-answers verify

install:
	uv sync

api:
	uv run uvicorn app.main:app --reload --port 8000

ui:
	uv run streamlit run streamlit_app.py --server.port 8501

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

eval-answers:
	uv run python -m evals.answers.run

verify:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy
	uv run pytest
