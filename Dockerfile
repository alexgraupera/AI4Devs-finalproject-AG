# The marketplace frontend, built once from its lockfile. Only its output reaches the final image:
# no Node, no node_modules, nothing that runs at request time.
FROM node:22-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json frontend/.npmrc ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_DEV=1

# Dependencies first, so code changes do not invalidate this layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project

COPY README.md ./
COPY app ./app
# The marketplace's web server, and the frontend it serves (built in the stage above).
COPY web ./web
COPY --from=frontend /frontend/dist ./frontend/dist
# The schema travels with the code that expects it, so the container can migrate itself.
COPY alembic.ini ./
COPY migrations ./migrations
COPY docker/entrypoint.sh ./docker/entrypoint.sh
RUN uv sync --locked

ENV PATH="/app/.venv/bin:$PATH"

# One image for both services: docker-compose.yml sets the command of each one. The entrypoint
# migrates when there is a database, then execs the command so it runs as PID 1.
#
# The port comes from PORT when the platform sets one (Render uses 10000) and is 8000 otherwise.
# The graceful shutdown gives a review in flight time to finish when a deploy stops the container:
# a model call takes seconds, not the milliseconds a default timeout assumes.
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --timeout-graceful-shutdown 90"]
