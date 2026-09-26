# 0024. The agent loop, its tools, and what the model is not trusted with

- **Status**: Accepted
- **Date**: 2026-09-25
- **Issue**: #38 (part of #3)

## Context

The listing review is a pipeline: one prompt with the regulatory checklist, one structured call. It cannot look anything up, so it can only cite the five articles its prompt carries, and it cannot say that a Catalan listing breaks article 61 of the Catalan law. The regulation Q&A can look things up, but reviews nothing. The final project asks for an agent with function calling and orchestration, and the course's first agent session builds one by hand: reason, act, observe, repeat, with a hard limit.

## Decision

**A second review path, `POST /api/v1/listings/agent-review`, next to the pipeline, not instead of it.** Both stay live, so #52 can measure what the agent buys for its extra calls. This is also where the three architectures meet in one request: the checklist travels in the prompt (CAG), the regulations are searched through a tool (RAG), and the model decides what to check and in which order (the agent).

**The loop is written by hand** (`app/generation/agentic/loop.py`), about a hundred lines, every decision a plain `if`. #41 re-expresses it as a graph and keeps it in the repository, so what the graph buys is measured against something that already works.

### The tools

| Tool | Runs | Why this way |
|---|---|---|
| `check_listing_fields` | Code, never the model | Which mandatory fields are empty and whether the text contradicts the price or the surface is an exact question. It takes **no arguments** and reads the listing under review: the model cannot check a different listing from the one it was given, and it spends no tokens copying it |
| `search_regulations` | The retriever, through a port | `agentic/` never imports `rag/`: the agent declares a `RegulationSearch` port and the conductor adapts the retriever to it. Arguments are validated in the tool, and a wrong one comes back as an error the model can read |
| `submit_review` | Validated here | The review is handed in **through a tool** whose parameters are the review schema, instead of as free text at the end. It is structured by construction; an invalid one goes back to the model with the schema errors |

A tool never raises into the loop. A failure, an unknown tool or malformed JSON becomes an observation: the model is told what went wrong and can correct itself. That is also what the session's example shows: a search that finds nothing, and a second one with other words that does.

### Hard exits

No agent loop without them: an impossible request otherwise loops until it has spent the budget or hit a provider's rate limit.

- **6 iterations**, **90 seconds**, or **the same call failing twice** with the same arguments.
- At any of them the model is made to submit what it has, once (`tool_choice` forced to `submit_review`), and the response carries the `stop_reason`, which the UI turns into "La revisión puede estar incompleta". If even that submission is invalid, the request fails with 502 rather than inventing a review.

### What the model is not trusted with

- **Citations.** The model names fragment numbers in `sources`; the conductor builds each citation from a fragment a search actually returned. A number no search returned is dropped and logged (`agent_review.invented_source`).
- **Legal findings without a source.** A finding with a legal basis must cite a fragment the agent read, or be one of the checklist points whose article travels in the prompt. Anything else is a legal claim nobody can check, and it is dropped before the user sees it (`guardrail.dropped_finding`, reason `unsourced`). Whether the cited fragment really *says* what the finding claims is a semantic check, and that is the critic of #40.
- **The verdict.** Recomputed from the findings that survive, as the pipeline does.
- **Everything before the model**: the input guardrails and the daily spend cap run before the first call.

### The trace

Every step (tool, arguments, a preview of the result, whether it failed, how long it took) goes back in the response, with **the text the model wrote next to its tool calls**: its reasoning, which the session asks to keep with every step. The UI shows it one click away; the log keeps `agent_review.completed` with the stop reason, the tools called, the fragments read, the tokens and the cost.

### The model

The generator of #47 (Claude Haiku 4.5). The session warns that weak models fail at tool use and cost more in retries than they save; whether Haiku is strong enough is measured in #52 on the listings dataset, with the failure classification of the traces, not assumed.

## Checked by hand, and a first iteration

Two listings through the real models (Claude Haiku 4.5, `text-embedding-3-large`), $0.049 in all:

| Listing | Prompt | Steps | What happened | Cost |
|---|---|---:|---|---:|
| Madrid: two months of deposit, agency fees on the tenant, no energy rating | v1 | 6 | Field check, four searches (label, deposit, fees, minimum information), submit. Three `high` findings citing RD 390/2021 art. 15, LAU art. 36 and art. 20, each with its BOE link | $0.012 |
| Barcelona: a clean studio, rating D | v1 | 6 | **Two errors.** It searched only the state rules, never the Catalan law; and it reported the energy rating as missing although the text says "Certificado energético D" and the field says D | $0.011 |
| Barcelona | **v2** | 7 | Decides the region first and searches the Catalan law: findings on article 61 (term, price update, last rent) and 66. No invented missing rating | $0.014 |
| Madrid | **v2** | 6 | The same three `high` findings and citations: v2 did not break the case v1 got right | $0.012 |

Prompt v2 adds two rules: decide the region from the municipality before searching, and check the listing, the structured fields and the field check before reporting a datum as missing. A second listing was worth more than a tenth test with a mocked model: both errors were invisible to the unit tests, because they are about what a real model does with the prompt. The listings dataset of #49 turns this kind of check into a measurement.

## Consequences

- An agent review costs several model calls: one per turn, each carrying the growing conversation. #52 measures it against the pipeline, step by step.
- The agent can cite any article of the corpus, not only the five of the checklist, which is the point: a Catalan listing gets the Catalan law.
- The loop keeps state in memory for the length of a request. A pause for a human (#42) needs that state to survive a restart, which is what the graph and its checkpointer bring in #41.
