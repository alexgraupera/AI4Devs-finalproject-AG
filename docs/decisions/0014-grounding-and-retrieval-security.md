# 0014. Grounding check and securing the retrieval service

- **Status**: Accepted
- **Date**: 2026-09-21
- **Issue**: #26 (part of #2)

## Context

Two gaps were left open on purpose until the retrieval was as good as it was going to get.

The citation check of #23 is **structural**: it proves the cited article was retrieved. A model can still cite a real article, with a working BOE link, for a rule that article does not contain — and that failure is invisible to everything upstream: the retrieval was right, the citation resolves, the link opens. Only reading both can catch it.

And the retrieval endpoints were open. Every query costs an embedding call and every answer costs three model calls, so an open endpoint is an open invoice.

## The grounding check

**Two deterministic pre-checks first, because they cost nothing**: an answer with no citation, or citing a fragment that is not in the context, is unsupported without asking anyone. Only what survives is worth a model call.

**Then a judge reads the cited articles and the answer**, extracts the legal claims and marks each as supported or not.

**The judge being unavailable does not condemn the answer.** A provider failure is not evidence that an answer is wrong, so the check fails open and logs it. The alternative — refusing every answer whenever the judge is down — turns a provider hiccup into an outage.

### The policy was wrong, and the measurement said so

The first version refused an answer if **any** claim was unsupported, on the reasoning that a reader cannot tell which sentence was the invented one. Measured over the 22 answerable golden questions, that policy **refused 23% of correct answers**. Reading what triggered them, most were not hallucinations at all:

| Rejected claim | What it really was |
|---|---|
| "Cada vez que se prorrogue el contrato, el arrendador puede exigir que la fianza se ajuste" | **In article 36.2.** The judge was simply wrong. |
| "La información mínima depende de si la vivienda está en Cataluña o en el resto de España" | Framing, not a legal claim. 18 of 19 claims were supported. |
| "en el resto de España, la LAU no regula quién paga la comisión" | A **negative** claim. No fragment can ever support one. |

An assistant that refuses one good answer in four is not a safer assistant, it is an unused one.

**Two changes, both from that evidence**: the prompt now explicitly excludes framing sentences, negative statements and cross-references from extraction, and the policy became a **confidence threshold of 0.7** — the share of claims the articles support — rather than all-or-nothing.

### What it does, measured over the 29 golden questions

| | Before this phase | After |
|---|---|---|
| Answerable questions answered | 100% (22/22) | **91% (20/22)** |
| Out-of-domain questions refused | 86% (6/7) | **100% (7/7)** |
| Cost per question | ~$0.013 | **~$0.014** |
| Latency per question | ~5 s | **~5.8 s** |

The refusal rate on out-of-domain questions reaching **100%** is the headline. ADR 0012 accepted one leak ("¿Cuánto cuesta el seguro de hogar?", retrieved at 0.5093) on the grounds that the generation would refuse it anyway. It does, and now the grounding check closes the gap from the other side: an answer that cannot be supported by the article it cites does not get published, whatever the similarity score said.

Of the two answerable questions not answered, only **one was refused by the grounding check** (`energy-label-display`, confidence 0.33, claiming display obligations the cited article does not state). The other (`agency-fees-paraphrase`) was the model itself declining to answer, which is a retrieval problem, not a grounding one.

**Cost**: about $0.001 and 0.8 s on top of an answer, because the judge only reads the cited articles rather than the whole context. It is the cheapest of the three model calls in the pipeline.

## Securing the retrieval layer

**An API key on the router, not on each endpoint.** `X-API-Key` is checked by a router-level dependency, so an endpoint added under `/regulations` is protected by being there rather than by someone remembering. A missing key and a wrong key get the same neutral 401: telling an attacker which of the two it was is free information.

**`/health` stays outside.** A probe that needs a secret stops working the day the secret rotates.

**An empty `RAG_API_KEY` leaves the corpus open**, which is right for local development and for the tests, and logs a warning **on every request** so it is never a silent state in production.

**A fixed window over Redis**, 30 requests per minute, keyed by API key and falling back to the client host so that unauthenticated callers do not share one bucket. Fixed rather than sliding: it admits a burst at a window boundary, which for a budget guard is an acceptable imprecision and one fewer moving part. 429 carries `Retry-After`, so a well-behaved client waits the right amount instead of retrying into the same wall.

**The limiter never takes the service down.** Redis unreachable means the request is allowed and the failure is logged. A rate limiter that turns an outage of an optional dependency into an outage of the product has its priorities backwards.

## Consequences

- An answer now costs three model calls (rerank, generation, grounding) for **~$0.014 and ~5.8 s**. `GROUNDING_ENABLED=false` and `RERANK_ENABLED=false` each remove one, with the measured quality cost stated in this record and in ADR 0013.
- The confidence threshold is a **dial, not a truth**: 0.7 was measured on 22 questions with one judge model. It should be re-measured whenever the answer prompt or the model changes, and the evaluation suite of #4 is where that belongs.
- The judge is the same cheap model that writes the answers. A stronger judge would probably make fewer of the mistakes seen above, at more cost per question; that trade is untested here.
- `grounding_failed` is logged with the claims that failed, so the failure rate is countable rather than anecdotal, and the dashboard of #4 can plot it.
- The corpus is no longer an open endpoint, but the API key is a single shared secret: per-caller keys, rotation and quotas belong to the production hardening of #5.
