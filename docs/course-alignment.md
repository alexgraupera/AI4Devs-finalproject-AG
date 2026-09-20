# Course alignment

This project is the final project of the LIDR **AI Engineering** master. It must apply what the programme teaches, on a domain of our own (Spanish rental listings) instead of the course's software estimator.

This document maps **every session of the programme** to where its content lives in this repository, and states what is deliberately left out and why. It is kept up to date as the plans are implemented.

- Reference project of the course: `ai-engineering/ai-service` (FastAPI). Our architecture mirrors its layering, see [`AGENTS.md`](../AGENTS.md) and [ADR 0001](decisions/0001-stack-and-project-structure.md).
- Plans live as GitHub issues, one per layer, under the `Final delivery` milestone.

**Status legend**: ✅ done · 🔜 planned (issue) · ⏭️ out of scope (with the reason)

## Final project requirements

| Requirement (final project lesson) | Where | Status |
|---|---|---|
| Repository based on `AI4Devs-finalproject`, branch `finalproject-AG`, tag `v1.0-final-AG` | This repository | 🔜 #5 |
| `README.md` with domain, architecture, components, setup, limitations | [`README.md`](../README.md) | 🔜 every phase updates its sections |
| AI service in FastAPI | `app/` | ✅ #7 |
| RAG pipeline over real data | `app/generation/rag/` | 🔜 #2 |
| Agent layer with function calling and orchestration | `app/generation/agentic/`, `app/domain/graph/` | 🔜 #3 |
| Documented evals (metrics, test set, ≥1 regression case) | `evals/` | 🔜 #4 |
| Deployment (public URL or 2-3 min video) | `docs/deployment.md` | 🔜 #5 |
| Frontend (recommended) | `streamlit_app.py` | ✅ #7 |
| Basic CI/CD (recommended) | `.github/workflows/` | ✅ #7 (verify), 🔜 #5 (deploy) |
| Repository policy: no `.env`, `.env.example`, no personal data, secret scanning | Repository root | ✅ / 🔜 #5 |

## Module 1 — Fundamentals of AI products

| Session | What it teaches | Where in this project | Status |
|---|---|---|---|
| S1: LLMs and environment | Provider APIs, reasoning parameters, tokenization, model comparison | `app/foundation/llm/`, ADR on model choice | 🔜 #1 (phases 2 and 4) |

## Module 2 — CAG (Cache Augmented Generation)

| Session | What it teaches | Where in this project | Status |
|---|---|---|---|
| S2: first CAG steps | FastAPI scaffolding, what CAG is, context management, scalable architecture | `app/`, layering | ✅ #7 |
| S3: model wrapper patterns | Provider abstraction and fallback (LiteLLM Router), smart caching, streaming, observability | `app/foundation/llm/wrapper.py`, `app/foundation/observability/` | 🔜 #1 (phases 4 and 5); streaming ⏭️ |
| S4: advanced AI products | Product interface, backend prompt templates (Jinja2), structured extraction (Instructor), guardrails, semantic cache | `app/foundation/prompts/`, `app/foundation/guardrails/`, `app/generation/cag/` | 🔜 #1 (phases 2, 3, 5) and #14 |
| S5: advanced features | Conversational memory, tier prompts, testing and evaluation of LLM systems, **Actor-Critic-Boss** | `app/generation/agentic/` (ACB), `evals/` | 🔜 #3, #4; memory and tier ⏭️ |

**Out of scope here, and why**

- **Streaming**: the review is a single structured JSON answer rendered as a form result, not a conversation; streaming a schema adds complexity without user value. Documented as a next step.
- **Conversational memory and the tier pattern**: reviewing a listing is a single-turn operation (paste listing → structured review). The multi-turn layer (`generation/conversation/`) would add sessions, history and compression with no use case behind them. The Actor-Critic-Boss pattern **is** adopted, because it raises the quality of the review itself.

## Module 3 — Data-driven AI

| Session | What it teaches | Where in this project | Status |
|---|---|---|---|
| S6: data foundations | Data quality, inventory and audit, multi-format extraction pipeline, cleaning, normalisation and validation, PII / GDPR in ingestion | `app/ingestion/`, [`docs/data-sources/`](data-sources/README.md) | ✅ sources audited; 🔜 #2 |
| S7: embeddings | Embedding model trade-offs, professional chunking strategies, chunking of the project's own data | `app/generation/rag/chunking/`, `app/generation/rag/embedding/` | 🔜 #2 |
| S8: vector databases | Why vector DBs, market state, index anatomy (HNSW / IVFFlat), schema design, tuning and pgvector's ceiling | `app/generation/rag/store/`, `alembic/` | 🔜 #2 |

Our corpus is Spanish legislation from the BOE (validated in [`docs/data-sources/`](data-sources/README.md)), so the ingestion layer covers download, parsing, normalisation and validation of the consolidated texts. PII anonymisation has no source here (public law), so the PII work lives in the **input guardrail** instead, where user-submitted listings can contain personal data.

## Module 4 — RAG architecture

| Session | What it teaches | Where in this project | Status |
|---|---|---|---|
| S9: RAG fundamentals | The four stages, query reformulation, top-k / threshold / filters, augmentation, securing the retriever as a data service | `app/generation/rag/retriever.py`, `app/api/` (API key + rate limiting) | 🔜 #2 |
| S10: retrieval techniques | Reranking and how to measure whether it pays, hybrid search, query expansion and decomposition, multi-index and routing, temporal filtering | `app/generation/rag/retrieval/` | 🔜 #2 (hybrid + reranking measured); multi-index routing ⏭️ |
| S11: advanced RAG | Content augmentation, synthesis of contradictory sources, verifiable citation, hallucination detection, embedding reindexing and versioning, RAGAS | `app/generation/rag/`, `evals/` | 🔜 #2 and #4 |

**Out of scope here, and why**

- **Multi-index and routing**: the course routes across three corpora (budgets, transcripts, technical docs). Ours is one homogeneous corpus (consolidated laws + resolutions), so routing would have a single destination. Documented as the natural extension when regional regulations are added.

## Module 5 — Agent orchestration

| Session | What it teaches | Where in this project | Status |
|---|---|---|---|
| S12: introduction to agents | Pipeline vs agent, anatomy of the loop, function calling (tools, schemas), tool design, agent cost | `app/generation/agentic/` | 🔜 #3 |
| S13: orchestration | LangGraph `StateGraph`, state and persistence (checkpointer), parallel execution and conditional routing, error handling, observability (Logfire) | `app/domain/graph/` | 🔜 #3 |
| S14: multi-agent systems | Supervisor, communication patterns, human-in-the-loop (`interrupt`), competition and synthesis, least privilege and audit | `app/domain/graph/` | 🔜 #3 (HITL, privilege and audit); supervisor ⏭️ |

**Out of scope here, and why**

- **Supervisor multi-agent**: with three tools and one review flow, a model-driven router would add cost and failure modes without a decision to make. The course's own criterion is that a multi-agent system must be more than "a graph with more nodes". Documented as a next step for when the system reviews several listing types.

## Module 6 — Production and measurement

| Session | What it teaches | Where in this project | Status |
|---|---|---|---|
| S15: deployment | Containerisation, self-contained images, migrations in the entrypoint, service boundary (`X-Service-Token` middleware + per-router API keys), CI/CD | `Dockerfile`, `docker-compose.yml`, `app/api/security.py`, `.github/workflows/` | ✅ containers (#7); 🔜 #5 |
| S16: measurement | Eval harness against the deployed service, regression gate (zero tolerance on safety), production dashboard from logged events, per-stage cost, A/B variants, deterministic output guardrail, human review routing | `evals/`, `app/foundation/guardrails/` | 🔜 #4 and #5 |

## Layering rules we inherit

From `ai-engineering/ai-service/ARCHITECTURE.md`, and enforced in our [`AGENTS.md`](../AGENTS.md):

- Each layer imports only from the layers above it: `config` → `foundation` → `domain/schemas` → `generation` → conductor → `api`.
- The `generation` siblings (`cag`, `rag`, `agentic`) **never import each other**: they compose only inside the conductor (`app/domain/`).
- `api/` is transport only; `dependencies.py` is the composition root and may import anything.
- New cross-layer composition goes in the conductor, never in a router and never through a sibling import.

## What is ours, on top of the base

- The domain: Spanish rental listing quality and compliance, instead of software estimation.
- The data: BOE consolidated legislation, stressed-area resolutions, Catastro and SERPAVI, validated and documented in [`docs/data-sources/`](data-sources/README.md) with runnable examples.
- The evaluation set: listings built on real properties, prices and regulation, annotated with their defects and the article each one breaks.
- The product decisions: what is a finding, what is informative, and what the system must never claim (a market price range is not a legal cap).
