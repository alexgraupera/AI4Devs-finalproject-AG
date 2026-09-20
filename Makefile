.PHONY: install api ui up down migrate ingest corpus-report corpus-drift verify

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

ingest:
	uv run python -m app.ingestion

corpus-report:
	uv run python -m app.ingestion.report

corpus-drift:
	uv run python -m app.ingestion.drift

verify:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy
	uv run pytest
