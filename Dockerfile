FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_DEV=1

# Dependencies first, so code changes do not invalidate this layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project

COPY README.md ./
COPY app ./app
COPY streamlit_app.py ./
RUN uv sync --locked

ENV PATH="/app/.venv/bin:$PATH"

# One image for both services: docker-compose.yml sets the command of each one.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
