# 0001. Stack and project structure

- **Status**: Accepted
- **Date**: 2026-09-19
- **Issue**: #7 (part of #1)

## Context

The final project must deliver an AI service in Python (FastAPI), a usable interface, and run locally with a single command. It is built by one person in about two weeks, with no infrastructure budget, and assessed on justified decisions. The course stack is Python, FastAPI, `uv`, Docker Compose and Streamlit/Gradio/Chainlit.

## Options considered

- **Interface**: Streamlit, Gradio, Chainlit, or a JavaScript frontend.
- **Layout**: our own structure, or the layering of the course reference project (`ai-engineering/ai-service`): `foundation/` / `domain/` / `generation/` / `api/`.
- **Database from day one** vs added when first needed.
- **Python version**: 3.11 (course minimum) or 3.12.

## Decision

- **Python 3.12 + `uv`** for dependencies and a reproducible lockfile. 3.12 instead of 3.11 because a transitive dependency of Streamlit (numpy) ships type stubs with 3.12-only syntax, which strict mypy cannot check under 3.11. The Docker image and the local environment use 3.12.
- **FastAPI** for the AI service (async, Pydantic contracts, OpenAPI docs) and **Streamlit** for the interface: it covers forms and structured results (not only chat) and can be deployed for free. The UI only talks to the API over HTTP.
- **Same layering as the course reference project**, in an `app/` package with tests mirroring it: `foundation/` (plumbing: LLM wrapper, prompts, guardrails, observability), `domain/` (schemas + conductor service), `generation/` (`cag/`, `rag/`, `agentic/`) and `api/` (thin routers). Each layer imports only from the layers above it, and the AI architectures compose only through the conductor. The final project is assessed against the programme's own architecture, and reusing it makes every session's material directly applicable; the rental domain, the public data sources and the evals are our own work on top.
- **One Docker image** for both services, with the command set per service in `docker-compose.yml`. The UI waits for the API health check.
- **No database yet**: PostgreSQL + pgvector is added in #2, with its first real use (the RAG corpus).
- **Quality gate**: `make verify` runs ruff (lint and format), mypy in strict mode and pytest, locally and in CI on every pull request.

## Consequences

- The structure matches the material taught in the master, so the sessions' code and explanations map directly onto this project.

- The AI logic can be tested, evaluated and deployed without the UI, and the UI could be replaced by another client.
- Streamlit is not meant for high concurrency; acceptable for a demo, and documented as a limitation.
- Strict typing adds some friction, but catches contract errors between layers early.
- The stack starts smaller; the database is added in the plan that needs it.
