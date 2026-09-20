"""Output guardrail: what the model says is not automatically what the user reads.

A finding that cites an article we never put in the checklist is either an invention or a
half-remembered one, and a wrong legal citation is worse than no citation at all. Those
findings are dropped, and the drop is logged so the evals can count it.
"""

import logging

from app.domain.schemas.listing_review import ListingReview, Verdict

log = logging.getLogger(__name__)

# The closed set of sources the checklist allows, verified against the consolidated BOE texts.
ALLOWED_LEGAL_BASIS = frozenset(
    {
        "RD 390/2021 art. 15.2",
        "LAU art. 36.1",
        "LAU art. 36.5",
        "LAU art. 20.1",
        "Ley 12/2023 art. 31",
    }
)


def check_review(review: ListingReview) -> ListingReview:
    """Drop findings citing a source outside the checklist, and keep the verdict consistent."""
    kept = []
    for finding in review.findings:
        if finding.legal_basis is not None and finding.legal_basis not in ALLOWED_LEGAL_BASIS:
            log.warning("guardrail.dropped_finding", extra={"legal_basis": finding.legal_basis})
            continue
        kept.append(finding)

    if len(kept) == len(review.findings):
        return review

    # The verdict was decided over the original findings, so it has to be recomputed: dropping
    # the only high finding must not leave a "request_changes" nobody can explain any more.
    verdict = Verdict.REQUEST_CHANGES if any(f.severity == "high" for f in kept) else Verdict.APPROVE
    return review.model_copy(update={"findings": kept, "verdict": verdict})
