# 0019. No semantic cache for listing reviews: measured, it serves the wrong review

- **Status**: Accepted
- **Date**: 2026-09-24
- **Issue**: #56 (closes #14)

## Context

#14 planned a semantic cache behind the exact-match one of [ADR 0007](0007-exact-match-cache.md): embed the listing, and when a new listing is close enough to one already reviewed, return that review without calling the model. The session on semantic caching builds one for the course project and warns about the case that decides whether it works: in its demo, "iOS and Android" and "only Android" hit the same cache entry at the default threshold, although they are different projects to estimate. It asks either to calibrate the threshold on your own data or to explain, with measurements, why a semantic cache does not fit the domain.

## The measurement

[`benchmarks/semantic_cache/`](../../benchmarks/semantic_cache/pairs.yaml): fourteen pairs of listings, embedded with the service's model, in three groups by what a cache hit would mean:

- **`reworded`**: the same flat and conditions, written differently. A hit saves a call and is right.
- **`clause-changed`**: the same flat with one condition changed that changes the review: a second month of deposit, agency fees moved to the tenant, the energy rating dropped, an extra guarantee of four months, the surface removed. A hit serves a clean review to a listing that breaks the law.
- **`different-flat`**: the easy negatives.

Every change is in the text. The structured fields would be part of the cache bucket and compared exactly, as the session does; the clauses that matter here live only in the description.

| Kind | `text-embedding-3-small` | `text-embedding-3-large` (the service's model) |
|---|---:|---:|
| `clause-changed` (a hit would be a wrong review) | **0.961 – 0.998** | **0.966 – 0.996** |
| `reworded` (a hit would be right) | 0.890 – 0.988 | 0.912 – 0.982 |
| `different-flat` | 0.527 – 0.698 | 0.534 – 0.686 |

The two groups are not just overlapping: **they are the wrong way round.** With the large model, the listing with a second month of deposit scores 0.996 against the original; the same listing with its sentences reordered scores 0.912. A threshold low enough to catch the rewordings (≤ 0.91) catches every changed clause as well; one high enough to exclude the changed clauses (> 0.996) catches nothing.

It is not a quirk of the model. The edits that change a legal verdict are the **smallest** edits a listing can receive, one word or one number, so they are exactly the ones an embedding of the whole text cannot see. A rewording moves every sentence; an illegal clause moves one digit.

Two models give the same picture, which is the point: it is a property of the task, not of the model. The next model will also find "fianza de una mensualidad" and "fianza de dos mensualidades" nearly identical, because they are.

## Decision

**No semantic cache for the listing review.** #14 is closed by this record.

The exact-match cache stays: it catches the resubmission of the same listing, measured at 1 ms and $0 ([ADR 0007](0007-exact-match-cache.md)), and it is safe by construction, because a single changed character changes the key.

## Consequences

- A repeated review with small edits pays for a new model call. That is the correct price: a small edit is exactly the kind that can change the verdict.
- The regulation Q&A is the place where a semantic cache could still pay ("¿Cuál es la fianza?" and "¿Cuánto es la fianza legal?" deserve the same answer), but the same inversion is likely ("¿puede pedir dos meses?" and "¿puede pedir tres?" do not). It is listed as a next step with this same harness, with question pairs instead of listings.
- `make benchmark-semantic-cache` re-runs the measurement for any embedding model in a few seconds and for a fraction of a cent.
