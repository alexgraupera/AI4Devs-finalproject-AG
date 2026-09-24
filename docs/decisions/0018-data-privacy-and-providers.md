# 0018. What data reaches which provider

- **Status**: Accepted
- **Date**: 2026-09-24
- **Issue**: #56

## Context

A listing is written by a landlord or an agency and can carry personal data: a phone number to call, an email, an owner's name, a bank account for the deposit. The service sends text to three external APIs. The course is explicit that provider promises are not guarantees, that personal data must be removed **before** it reaches a model and never by asking the model to ignore it, and that a project in a regulated area should say where it stands. None of that was written down.

## What goes where

| Data | Leaves to | Why |
|---|---|---|
| Listing text and its structured fields | Anthropic (primary) or OpenAI (fallback) | The review |
| Listing text, question text | OpenAI moderation | The last input guardrail |
| Question text | OpenAI embeddings, then Anthropic or OpenAI | Retrieval, reranking, answer, grounding check |
| BOE articles | The same providers, as context | Public law: nothing to protect |

What the service **keeps**: no listings and no questions. The cache stores the review under a hash of the prompt ([ADR 0007](0007-exact-match-cache.md)); logs carry lengths, tokens and costs, never the text; the database holds only the public corpus. The agent's audit (#43) redacts tool arguments and the feedback table (#51) stores no text, by the same rule.

## Decision

**Personal data is rejected at the door, not redacted and not left to the prompt.** Emails, Spanish phone numbers and IBANs are caught by the input guardrail before any network call and the request is refused with a message that says what to remove ([ADR 0004](0004-guardrails.md)). Rejecting rather than masking is deliberate: a masked email becomes a listing its author did not write, and the person publishing needs to know.

**Asking the model not to repeat personal data is not a control**, and nothing in the service relies on it.

## What this does not cover

- **Names, ID numbers (DNI/NIE) and street addresses are not detected.** They are harder than a regex: a name is also a street, and an address is a legitimate part of a listing. The next step is Microsoft Presidio with a Spanish model and the DNI/NIE recognisers, masking identifiers the listing does not need while keeping the location; the session on data quality uses it for exactly this.
- **Quasi-identifiers** (age, profession, "vive aquí una familia con dos niños") are left alone: in a rental listing they describe the flat's current use more than a person, and removing them would break the review.
- **Provider terms.** Both providers state that API data is not used to train their models by default and is retained for a limited period for abuse monitoring. A real marketplace would sign each provider's data processing agreement, check where the data is processed, and prefer the providers' EU processing options where they exist. This project avoids the question by design: no personal data is sent.

## Consequences

- The PII layer is part of the privacy story, not only a guardrail: its false negatives (names, DNI) are listed in the README limitations.
- Adding a data source or a tool that handles personal data (the Catastro lookup of #6 would use cadastral references, which are not personal but can point to one) starts by adding its row to the table above.
