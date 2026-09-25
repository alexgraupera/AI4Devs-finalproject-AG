# Scope and roadmap

The system reviews Spanish rental listings: a landlord or agency pastes a listing and gets a structured review of what is missing, inconsistent or non-compliant, grounded in the regulations published in the BOE, plus a Q&A over those regulations.

This document states what the system covers, what it deliberately does not, and why. It is kept up to date as the plans are implemented.

**Status**: ✅ done · 🔜 planned (issue)

## Capabilities

### CAG: knowledge in the prompt, and caches in front of it

As in the course, CAG is the prompt assembled from stable knowledge plus the cache that avoids asking twice. Here the stable knowledge is the regulatory checklist: five legal points, each with the article that backs it, small and stable enough to travel in every prompt instead of being retrieved.

| Capability | Status |
|---|---|
| Regulatory checklist in the versioned system prompt, with a closed set of citable articles | ✅ #8 |
| Exact-match cache (SHA-256 over the full prompts and generation parameters, with TTL) | ✅ #12 |
| Semantic cache: measured and **not built**, because no threshold separates a reworded listing from one with an illegal clause changed | ✅ #56 |

### Generation and quality

| Capability | Status |
|---|---|
| Versioned Jinja2 prompts, so prompt iteration is visible in the Git history | ✅ #8 |
| Structured output validated against the domain schema, with re-prompting on invalid output | ✅ #8 |
| Input guardrails: size limits, moderation, prompt-injection and PII heuristics | ✅ #9 |
| Output guardrails: scope filter and a deterministic check that routes implausible reviews to human review | ✅ #9, 🔜 #5 |
| Provider fallback (Anthropic primary, OpenAI secondary), cost per call and structured logging | ✅ #10 |
| A model per role (the judge on the other provider), and every call bounded: timeout, token budget, temperature, named truncation | ✅ #47 |

### RAG — retrieval over the regulations

| Capability | Status |
|---|---|
| Ingestion of the BOE corpus: download, parse, normalise and validate, idempotently | ✅ #21, #28 |
| Chunking by article, compared against a fixed-size baseline | ✅ #28 |
| Embeddings in PostgreSQL + pgvector, schema and indexes in migrations, with model and corpus version stored per chunk | ✅ #20, #22 |
| Top-k with a measured threshold and metadata filters (law, jurisdiction) | ✅ #22 |
| Embedding model compared on the golden set (`text-embedding-3-large` at 1,536 dimensions: answered 82% → 91%), threshold swept per model | ✅ #56 |
| Why RAG and not the whole corpus in the prompt or fine-tuning, with numbers (187,883 tokens, 94% of the window) | ✅ #56 |
| Query reformulation: built, measured, **deleted** (it halved the refusal rate) | ✅ #25 |
| Reranking with a model that reads the candidates (recall@1 82% → 91%) | ✅ #25 |
| Hybrid search: built, measured, **deleted** (it made retrieval worse) | ✅ #25 |
| Answers grounded in the retrieved context, with verifiable citations | ✅ #23 |
| Hallucination checks over the generated answer (out-of-domain refusals 86% → 100%) | ✅ #26 |
| Corpus drift detection: a weekly check opens an issue when the BOE updates a source | ✅ #28 |
| Retrieval endpoints secured with an API key and rate limited | ✅ #26 |

### Agents

| Capability | Status |
|---|---|
| Agent loop with function calling: validate fields (in code), search the regulations, submit a validated review, with hard exits and a trace | ✅ #38 |
| Rewrite the listing from the final findings, with gaps for data it cannot invent and new figures flagged in code; editable in the UI | ✅ #39 |
| Actor-critic-boss: a critic on the other provider judges each finding against the listing and the whole cited article; the boss accepts, retries once or escalates | ✅ #40 |
| Graph orchestration (LangGraph) with typed JSON state, reducers, conditional routing and a Postgres checkpointer; nothing kept once a run ends | ✅ #41 |
| Human-in-the-loop: an escalated review pauses before publishing (`interrupt`), and resumes with a person's decision (approve, adjust, reject), on any process | ✅ #42 |
| Least privilege over tools (a role table, deny by default, checked before execution), with an audit event for every call | ✅ #43 |
| Property data (Catastro) and market rent range (SERPAVI) as agent tools | 🔜 #6 |

### Evaluation

| Capability | Status |
|---|---|
| Golden sets: regulation Q&A with reference answers, conflicts and a regression case; annotated listings | ✅ #24, #48, #49 |
| Listing review metrics (precision, recall and F1 of legal findings, clean false positives, verdict, adversarial handling), pipeline and agent on the same listings | ✅ #49, #52 |
| Agent vs pipeline: cost broken down by step (API and UI), failures classified by the step that lost them, repeated runs | ✅ #52 |
| Retrieval metrics (recall@k, MRR) over a golden set, per technique | ✅ #24 |
| Generation metrics (faithfulness, relevance, correctness, citation accuracy) with a judge on the other provider | ✅ #48 |
| Cost and latency per stage | ✅ #48 |
| Regression gate against a promoted baseline, with zero tolerance on safety metrics; mocked regression cases in CI; real evals in a manual or weekly workflow | ✅ #50 |
| A/B comparison of prompt and retrieval variants | ✅ #48 (named variants per run) |
| User feedback (👍/👎 and a comment) under every review and answer, linked by `request_id` to the log events of the request; comments with personal data masked | ✅ #51 |
| Dashboard built from the events the service already logs | Out of scope until the production measurement session (see #4) |

### Production

| Capability | Status |
|---|---|
| Containers for the whole stack, self-contained image, migrations and corpus bootstrap on start-up | ✅ #7, #53, #54 |
| CI running lint, typecheck, tests (database-backed included) and a secret scan on every pull request | ✅ #7, #22, #54 |
| Service token middleware plus per-router API keys and rate limiting, fail fast in production | ✅ #53 |
| Daily spend cap that stops model calls, liveness and readiness probes | ✅ #53 |
| Public deployment on Render from `main`, described as a Blueprint | ✅ #54 (live once the Blueprint is created) |

## Out of scope, and why

- **Semantic cache for listing reviews**: measured in ADR 0019. The same flat with a second month of deposit is more similar to the original (0.996) than the same flat reworded (0.912), so any threshold that saves calls serves a clean review to an illegal listing.

- **Streaming responses**: the output is a validated JSON review rendered as a form result, not a conversation. Streaming a schema adds machinery without changing what the user sees.
- **Conversational memory and per-profile prompt tiers**: reviewing a listing is a single-turn operation. Sessions, history and history compression would be infrastructure without a use case behind them.
- **Multi-index routing**: the corpus is homogeneous (consolidated laws and resolutions), so a router would always have a single destination. It becomes worthwhile when regional regulations are added as separate collections.
- **Supervisor-driven multi-agent system**: with three tools and one review flow, letting a model decide what runs next adds cost and failure modes without a real decision to make. It becomes worthwhile when the system reviews several listing types with different flows.

Each of these is listed in the README as a next step, with the condition that would justify building it.

## Delivery checklist

| Requirement | Where | Status |
|---|---|---|
| Branch `finalproject-AG` and tag `v1.0-final-AG` | This repository | 🔜 #5 |
| `README.md` with domain, architecture, components, setup and limitations | [`README.md`](../README.md) | 🔜 updated by every phase |
| AI service in FastAPI | `app/` | ✅ #7 |
| RAG pipeline over real data | `app/ingestion/`, `app/generation/rag/` | ✅ #2 |
| Agent layer with function calling and orchestration | `app/generation/agentic/`, `app/domain/graph/` | 🔜 #3 |
| Documented evals: metrics, test set and at least one regression case | `evals/`, [`docs/evals.md`](evals.md) | ✅ #48, #49, #50, #52 |
| Deployment: public URL or a 2-3 min video | `docs/deployment.md` | 🔜 #5 |
| Frontend (recommended) | `streamlit_app.py` | ✅ #7 |
| Basic CI/CD (recommended) | `.github/workflows/` | ✅ #7, 🔜 #5 |
| No secrets or personal data in the repository, `.env.example` up to date | Repository root | ✅ / 🔜 #5 |

## Layering rules

- Each layer imports only from the layers above it: `config` → `foundation` → `domain/schemas` → `generation` → conductor → `api`.
- `ingestion/` is offline: it builds the corpus the retrieval reads, imports only `config` and `foundation/`, and nothing in the request path imports it. It runs as a command, never inside a request.
- The `generation` siblings (`cag`, `rag`, `agentic`) never import each other: they compose only inside the conductor in `app/domain/`.
- `api/` is transport only: no business logic, just error mapping.
- `dependencies.py` is the composition root and may import anything; nothing else may import it except routers and tests.
- New composition between layers goes in the conductor, never in a router and never through a sibling import.
