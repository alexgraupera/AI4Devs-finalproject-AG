# Scope and roadmap

The system reviews Spanish rental listings: a landlord or agency pastes a listing and gets a structured review of what is missing, inconsistent or non-compliant, grounded in the regulations published in the BOE, plus a Q&A over those regulations.

This document states what the system covers, what it deliberately does not, and why. It is kept up to date as the plans are implemented.

**Status**: ✅ done · 🔜 planned (issue)

## Capabilities

### CAG — caches

Answer without calling the model when an equivalent review already exists.

| Capability | Status |
|---|---|
| Exact-match cache (SHA-256 over the full prompts and generation parameters, with TTL) | ✅ #12 |
| Semantic cache over the review embeddings, with a justified similarity threshold | 🔜 #14 |

### Generation and quality

| Capability | Status |
|---|---|
| Versioned Jinja2 prompts, so prompt iteration is visible in the Git history | ✅ #8 |
| Structured output validated against the domain schema, with re-prompting on invalid output | ✅ #8 |
| Input guardrails: size limits, moderation, prompt-injection and PII heuristics | ✅ #9 |
| Output guardrails: scope filter and a deterministic check that routes implausible reviews to human review | ✅ #9, 🔜 #5 |
| Provider fallback (Anthropic primary, OpenAI secondary), cost per call and structured logging | ✅ #10 |

### RAG — retrieval over the regulations

| Capability | Status |
|---|---|
| Ingestion of the BOE corpus: download, parse, normalise and validate, idempotently | ✅ #21, #28 |
| Chunking by article, compared against a fixed-size baseline | ✅ #28 |
| Embeddings in PostgreSQL + pgvector, schema and indexes in migrations, with model and corpus version stored per chunk | ✅ #20, #22 |
| Top-k with a measured threshold and metadata filters (law, jurisdiction) | ✅ #22 |
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
| Agent loop with function calling: search the regulations, validate fields, rewrite the listing | 🔜 #3 |
| Actor-critic-boss: findings without a supporting citation do not reach the user | 🔜 #3 |
| Graph orchestration with typed state, conditional routing and persistence | 🔜 #3 |
| Human-in-the-loop: the run pauses before publishing when confidence is low, and resumes with the human decision | 🔜 #3 |
| Least privilege over tools, with an audit trail of every agent action | 🔜 #3 |
| Property data (Catastro) and market rent range (SERPAVI) as agent tools | 🔜 #6 |

### Evaluation

| Capability | Status |
|---|---|
| Golden sets: regulation Q&A, annotated listings and adversarial cases | ✅ #24 (retrieval), 🔜 #4 (the rest) |
| Retrieval metrics (recall@k, MRR) over a golden set, per technique | ✅ #24 |
| Generation metrics (faithfulness, correctness, citation accuracy) | 🔜 #4 |
| Cost and latency per stage | 🔜 #4 |
| Regression gate against a promoted baseline, with zero tolerance on safety metrics | 🔜 #4 |
| A/B comparison of prompt and retrieval variants | 🔜 #4 |
| Dashboard built from the events the service already logs | 🔜 #4 |

### Production

| Capability | Status |
|---|---|
| Containers for the whole stack, self-contained image, migrations on start-up | ✅ #7, 🔜 #5 |
| CI running lint, typecheck and tests on every pull request, database-backed tests included | ✅ #7, #22 |
| Service token middleware plus per-router API keys and rate limiting | 🔜 #5 |
| Public deployment (or a recorded walkthrough) and spend limits on the providers | 🔜 #5 |

## Out of scope, and why

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
| Documented evals: metrics, test set and at least one regression case | `evals/` | 🔜 #4 |
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
