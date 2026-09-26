FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_DEV=1

# Dependencies first, so code changes do not invalidate this layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project

COPY README.md ./
COPY app ./app
COPY streamlit_app.py ui_api.py ./
# Streamlit discovers the pages next to the entry point: without them the UI is a landing page.
COPY pages ./pages
# The schema travels with the code that expects it, so the container can migrate itself.
COPY alembic.ini ./
COPY migrations ./migrations
COPY docker/entrypoint.sh ./docker/entrypoint.sh
RUN uv sync --locked

ENV PATH="/app/.venv/bin:$PATH"

# One image for both services: docker-compose.yml sets the command of each one. The entrypoint
# migrates when there is a database, then execs the command so it runs as PID 1.
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
