# 0028. The corrected listing: rewritten from the final findings, never with invented data

- **Status**: Accepted
- **Date**: 2026-09-25
- **Issue**: #39 (part of #3)

## Context

A review is a list of problems. The person publishing still has to turn it into a listing, and the user story of #3 asks for the agent to "propose a corrected listing" they can accept or edit. The risk is specific: a rewrite can make a listing compliant by making it false (a surface, a price or an energy rating the owner never gave), and a compliant, false listing is worse than a merely non-compliant one.

## Decision

**A rewrite step after the findings are final, not a tool the agent calls mid-loop.** The plan had `rewrite_listing` as a third tool of the actor. It moved because of when it would run: mid-loop, the actor would rewrite from findings the critic may still reject or a person may still drop, and the corrected listing would fix problems that were never there. So the rewrite runs once, on the findings that survived the critic, the evidence and citation checks and, for a paused review, the person's decision (`approve` or `adjust`; a discarded review is not rewritten). A review without findings is not rewritten at all: nothing is paid for a rewrite with nothing to fix.

**The prompt fixes only the findings**, keeps the tone and length, never adds a fact the listing does not state, and leaves a gap in square brackets for a mandatory datum it cannot invent (`[indica la calificación energética]`).

**Code checks the one thing a rewrite must not do.** Every figure in the rewrite that the original listing (text and structured fields) does not state is reported next to it as `new_figures`, and the UI asks the person to check them. It does not reject the rewrite: "una mensualidad" has no digit, but a legitimate correction could, and the person decides. Figures inside a placeholder are not counted.

**The person has the last word**: the UI shows the corrected listing in an editable text area, with the changes the model says it made and the gaps to fill.

## Checked on the real models

The Madrid listing (two months of deposit, fees on the tenant, no energy rating), through the graph with the critic, $0.021 for the whole review:

> Piso exterior de 2 habitaciones en Chamberí, 65 m² útiles, reformado, con ascensor y calefacción. Calificación energética: **[indica la calificación energética]**. Precio: 1.350 €/mes, sin incluir **[indica si incluye o no suministros, comunidad, IBI u otros conceptos]**. **La propiedad asume los gastos de agencia** y de formalización del contrato. **Fianza de una mensualidad**. Disponible ya.

Both violations corrected, both missing data left as gaps, **no new figures**.

## Consequences

- One more model call per review with findings (~$0.002-0.003).
- `adjust` on a paused review works on the findings; the corrected listing follows from them. A person editing the corrected text is the UI's text area, not a round trip to the agent.
- The rewrite is the generator's output and is not judged by the critic. Its check is deterministic and narrow (figures); a rewrite that changes a meaning without a figure is caught only by the person reading it, which is why it is shown next to the original findings rather than published on its own.
