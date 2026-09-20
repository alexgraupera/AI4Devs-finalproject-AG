# 0009. Chunking strategy and corpus source

- **Status**: Accepted
- **Date**: 2026-09-20
- **Issue**: #28 (part of #2)

## Context

The corpus is 364 items and ~617k characters of Spanish legislation. How it is cut up decides two things at once: what the retrieval can find, and what the answer can cite. A citation that does not point at a specific article is not verifiable, and an unverifiable citation is the failure mode this whole project exists to avoid.

## Decision

**One chunk per article.** An article is the unit a citation points at, so it is the unit a chunk should be. The alternative, fixed-size chunks with overlap, was implemented (`fixed_size_chunks`) and measured over the same corpus:

| | Article chunking (`max_chars=6000`) | Fixed size (1,000 / 200 overlap) |
|---|---|---|
| Chunks from 353 articles | 369 | 768 |
| Articles split | 13 (3.7%) | 207 (58.6%) |
| **Chunks spanning more than one article** | **0, by construction** | **363 (47.3%)** |
| Size p50 / p95 / max | 1,248 / 5,253 / 5,989 | ~1,000 flat |

Nearly half the fixed-size chunks straddle two or more articles. Retrieving one of those means the model is handed a fragment ending in one rule and starting another, and no citation can be attached to it honestly. That is the decisive number, not the chunk count.

**`max_chars = 6000`**, chosen from the measured distribution rather than from a model limit (`text-embedding-3-small` accepts ~30k characters, so the model is not the constraint):

| `max_chars` | Articles split |
|---|---|
| 2,000 | 97 (27.5%) |
| 4,000 | 26 (7.4%) |
| **6,000** | **13 (3.7%)** |
| 8,000 | 7 (2.0%) |

At 6,000 the citation stays exact for 96% of articles, and the worst case of five retrieved chunks is ~30k characters of context (~7.5k tokens), which leaves room for the question and the answer in any cheap model. Lower budgets split a quarter of the corpus for no retrieval benefit this corpus size justifies.

**Splits land on paragraph boundaries, never mid-sentence.** The longest paragraph in the whole corpus is 1,358 characters, comfortably under the budget, so the splitter always has somewhere to break. A paragraph longer than the budget is emitted whole rather than cut: an oversized chunk is a worse embedding, a truncated sentence is a wrong rule.

**Every continuation piece is prefixed with the article title.** A chunk that starts at "2. Durante los cinco primeros años..." is a rule with no subject, and that is what the model would have to answer from.

**Re-ingestion is idempotent at two levels.** `/metadatos` (1.3 KB) decides whether to download the text at all; `content_hash` per chunk decides whether to rewrite a row. Measured on the real corpus: the first run writes 380 chunks in 1.5 s, the second skips every source in 0.56 s without downloading a byte of text, and `--force` rewrites nothing because all 380 hashes match. From #22 onwards that is also what stops a re-ingestion from paying to embed the corpus again.

**An article that disappears from a source is deleted.** A repealed or renumbered article that survives in the corpus is an assistant citing rules that no longer exist.

## The corpus source: the BOE API, not a derived copy

[`legalize-es`](https://github.com/legalize-dev/legalize-es) publishes Spanish consolidated legislation as Markdown, one file per law and one commit per reform. It is well built, actively maintained and draws from the same BOE open data API, and its git-history-as-reform-log is a genuinely elegant idea. It was considered and not adopted, for three reasons:

- **It carries no block identifiers.** Citations here are deep links such as `act.php?id=BOE-A-2023-12203#a3-3`, and block ids are not article numbers: article 31 of Ley 12/2023 lives in block `a3-3`. Their Markdown has no anchors, so the deep link cannot be built from it without querying the BOE index anyway.
- **It does not cover the stressed-areas resolutions** (both return 404): those are daily BOE items, not consolidated legislation, so two of the six sources would need their own client regardless.
- **It is a derived work.** Our citations would inherit a third party's parsing fidelity. For an assistant whose purpose is to be checkable, reading the official source directly is the defensible position.

Its licensing would have been no obstacle (BOE reuse terms, attribution required).

## Consequences

- 380 chunks in the database, p95 of 5,253 characters. Embedding cost is estimated in #22 against these numbers.
- The `(document_id, block_id, ordinal)` unique constraint of #20 is what makes the idempotency real rather than intended.
- Splitting affects 13 articles, all of them long transitional or additional provisions. If retrieval later shows those specific chunks underperforming, lowering `max_chars` is a configuration change plus a re-ingestion, not a redesign.
- The fixed-size baseline stays in the codebase, used by nothing. It is the evidence behind this decision, and #24 will reuse it if the question is ever reopened with retrieval metrics instead of structural ones.
- Re-running the ingestion is cheap enough to be a habit, and `make corpus-drift` plus the weekly workflow say when it is needed.
