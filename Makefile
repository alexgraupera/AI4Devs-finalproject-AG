.PHONY: install api ui up down verify

install:
	uv sync

api:
	uv run uvicorn rental_assistant.api.app:app --reload --port 8000

ui:
	uv run streamlit run src/rental_assistant/ui/app.py --server.port 8501

up:
	docker compose up --build

down:
	docker compose down

verify:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy
	uv run pytest
