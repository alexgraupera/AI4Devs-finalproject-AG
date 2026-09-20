.PHONY: install api ui up down migrate ingest embed corpus-report corpus-drift verify

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

verify:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy
	uv run pytest
