# AGENTS.md

Final project of the LIDR AI Engineering master: a **rental listing quality and compliance assistant** for a Spanish real estate marketplace. A landlord or agency pastes a rental listing and gets a structured review of missing, inconsistent or non-compliant information, grounded in Spanish regulations (BOE), plus a Q&A over those regulations.

The system follows the course architecture: CAG → RAG → agents → evals → deployment. Built only on public data and with a zero infrastructure budget.

## Planning

- The work is planned as GitHub issues, one parent issue per layer (labelled `plan`), all under the `Final delivery` milestone (2026-10-06).
- Plans are created with `/codely-plan-create-github <issue-url>` and implemented one phase at a time with `/codely-plan_phase-implement-github <issue-url>`: one branch and one pull request per phase, merged by the user.
- Each parent issue lists the knowledge to demonstrate and the decisions to justify. Keep them in mind while implementing: the project is assessed on justified decisions, not only on working code.

## Stack

- Python 3.12+ managed with `uv`.
- FastAPI + Uvicorn (AI service), Pydantic (contracts and LLM output validation).
- Streamlit (UI).
- PostgreSQL + pgvector (vector store).
- Docker Compose for the local environment.
- LLM providers: Anthropic and OpenAI, behind a provider abstraction. Cheap models by default (cost matters: API credits only).

## Commands

- `make install`: install dependencies (`uv sync`).
- `make up` / `make down`: start / stop the whole stack with Docker Compose (API on `:8000`, UI on `:8501`).
- `make api` / `make ui`: run the API or the UI locally with hot reload.
- `make verify`: lint (ruff), format check (ruff), typecheck (mypy strict) and tests (pytest). Run it before every commit; CI runs it on every pull request.

## Project structure

- `src/rental_assistant/`: application package, organised by module (`api/`, `ui/`, `config.py`; `listing_review/`, `llm/` and `prompts/` are added by the next phases).
- `tests/`: tests mirroring the package structure.
- `docs/decisions/`: architecture decision records.
- `docs/data-sources/`: data source guides and runnable examples.

## Conventions

- Code, docs, issues, pull requests and commits in English. User-facing copies in Spanish. `README.md` and `prompts.md` follow the LIDR template in Spanish.
- Commits and pull request titles follow Conventional Commits.
- Prompts live in versioned files, never as inline strings, so prompt iteration is visible in the Git history.
- Technical decisions are recorded in `docs/decisions/` (one file per decision: context, options considered, decision, consequences).
- Data sources are documented in [`docs/data-sources/`](docs/data-sources/README.md): one guide per source (endpoints, real responses, gotchas) with runnable examples in `docs/data-sources/examples/`. Reuse their parsing rules and gotchas when implementing clients, and update the guide if a source changes.
- Tests never call real LLM APIs: mock the provider. Evals are the only code allowed to call real models.
- Secrets only through environment variables (`.env`, never committed; keep `.env.example` updated).
- Relevant prompts used to build the project with AI are logged in `prompts.md`.

## Documentation

- `README.md` keeps the LIDR `AI4Devs-finalproject` template sections (0-7) plus the sections marked 🆕 required by the AI Engineering final project and repository policy (AI architecture, latency/cost/quality/security, traceability, decisions, evals, limitations). Never remove template sections.
- When a phase changes something covered by a README section, update that section in the same pull request.
- Never commit `.env`, credentials or personal data; document every required variable in `.env.example`.
