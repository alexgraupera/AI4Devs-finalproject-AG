# AGENTS.md

Final project of the LIDR AI Engineering master: a **rental listing quality and compliance assistant** for a Spanish real estate marketplace. A landlord or agency pastes a rental listing and gets a structured review of missing, inconsistent or non-compliant information, grounded in Spanish regulations (BOE), plus a Q&A over those regulations.

The system stacks the layers of a production AI product: CAG (the regulatory checklist in the prompt, and the caches in front of the model), RAG (retrieval over Spanish regulations), agents, evaluation and deployment. Built only on public data and with a zero infrastructure budget.

## Planning

- [`docs/scope.md`](docs/scope.md) lists the capabilities the system covers, what is deliberately out of scope and why, and the delivery checklist. Check it before planning or implementing, and keep it up to date.

- The work is planned as GitHub issues, one parent issue per layer (labelled `plan`), all under the `Final delivery` milestone (2026-10-06).
- Plans are created with `/codely-plan-create-github <issue-url>` and implemented one phase at a time with `/codely-plan_phase-implement-github <issue-url>`: one branch and one pull request per phase, merged by the user.
- Each parent issue lists the knowledge to demonstrate and the decisions to justify. Keep them in mind while implementing: the project is assessed on justified decisions, not only on working code.

## Stack

- Python 3.12+ managed with `uv`.
- FastAPI + Uvicorn (AI service), Pydantic (contracts and LLM output validation).
- Marketplace frontend in `frontend/` (it replaced the Streamlit client in #89, ADR 0036): Vite + React + TypeScript, React Router, Tailwind CSS, Vitest + Testing Library (jsdom), ESLint. Node 22 (`frontend/.nvmrc`); `frontend/.npmrc` enables `legacy-peer-deps` to work around an npm 10 peer resolution bug with Vitest 5.
- PostgreSQL + pgvector (vector store).
- Docker Compose for the local environment.
- LLM access through a wrapper built with LiteLLM (`Router` with primary + fallback) and Instructor (validated structured output with re-prompting). Anthropic primary, OpenAI fallback, switchable by configuration. Cheap models by default (cost matters: API credits only). `litellm` is pinned to an exact version.
- Versioned Jinja2 prompts, structured logging with `structlog`, and an own model price table (looked up by longest matching prefix, so dated model snapshots are priced instead of silently costing zero).

## Commands

- `make install`: install dependencies (`uv sync` and `npm --prefix frontend ci`).
- `make up` / `make down`: start / stop the whole stack with Docker Compose (API on `:8000`, marketplace on `:8080`).
- `make api`: run the API locally with hot reload.
- `make frontend`: run the marketplace frontend locally on `:5173` with hot reload. Its `/api` and `/bff` calls go to `make web`.
- `make web`: run the marketplace's web server locally on `:8080`: it serves `frontend/dist` and forwards the frontend's API calls with the credentials.
- `make verify`: lint (ruff), format check (ruff), typecheck (mypy strict) and tests (pytest), then the frontend's typecheck, lint, tests and build (`npm --prefix frontend run verify`). Run it before every commit; CI runs it on every pull request.

## Project structure

- `app/`: application package. Each layer may only import from the layers above it:
  - `main.py`, `config.py`, `dependencies.py`: composition root, above the layers.
  - `foundation/`: plumbing with no AI-architecture opinion (`llm/`, `prompts/`, `guardrails/`, `observability/`, `persistence/`).
  - `domain/`: the contract (`schemas/`) and the conductor service that composes the pipeline.
  - `generation/`: the AI architectures (`cag/` caches, `rag/` retrieval, `agentic/` agents). They never import each other: they compose only through the conductor.
  - `api/`: thin routers (transport), no business logic.
- `frontend/`: the marketplace (Umbral), the product's interface; it only talks to the API through `web/`. Fictional listings, agencies and photos (`src/catalogue/listings.ts`, `public/photos/` with `CREDITS.md`), real tools. Tests live next to the code (`*.test.ts(x)`); `src/testing/stubApi.ts` fakes the web server, so no frontend test reaches the network. It calls the API only through `src/api/client.ts`. The landlord's listings live in `src/landlord/myListingsStore.ts` (persisted in `localStorage` under `umbral-my-listings`; the demo has no marketplace database); components read them through `useMyListings()`.
- `web/`: the marketplace's own backend (FastAPI + httpx, no new dependency). It serves the built frontend and forwards to the API only the calls listed in `web/forwarding.py`, adding the service token and the API key, so no secret reaches the browser (ADR 0020). Add an endpoint to that list only when the frontend starts using it. The shared login of the demo lives in `web/session.py` (ADR 0034, 0036): the pages are public, every forwarded call needs a session, and production fails closed without `UI_USERNAME`, `UI_PASSWORD` and `SESSION_SECRET`. Tests in `tests/web/` replace the API with an `httpx.MockTransport` and never read the developer's `.env` for these settings.
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
- Frontend styles use only the design tokens of `frontend/src/index.css` (Tailwind's default palette is switched off): add a new colour there, never in a class. The marketplace never uses a real portal's name, logo or photos, and every page shows the demo notice.

## Documentation

- `README.md` keeps the LIDR `AI4Devs-finalproject` template sections (0-7) plus the sections marked 🆕 required by the AI Engineering final project and repository policy (AI architecture, latency/cost/quality/security, traceability, decisions, evals, limitations). Never remove template sections.
- When a phase changes something covered by a README section, update that section in the same pull request.
- Never commit `.env`, credentials or personal data; document every required variable in `.env.example`.
