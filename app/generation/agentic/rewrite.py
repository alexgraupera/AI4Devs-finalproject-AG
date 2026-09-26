"""The corrected listing: the review becomes something the person publishing can act on.

It runs once the findings are final, after the critic and after a person's decision, and not as a
tool the agent may call mid-loop: a rewrite made from findings the critic later rejects would fix
problems that were never there (ADR 0028).

The model rewrites; code checks the one thing a rewrite must never do, invent data. Every figure in
the rewrite that the original listing does not state is reported next to it, so a compliant but
false listing cannot pass for a corrected one unnoticed.
"""

import re
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from app.domain.schemas.listing_review import Finding, Listing
from app.foundation.llm.usage import LLMUsage
from app.foundation.llm.wrapper import StructuredLLM
from app.foundation.prompts.loader import render_agent_rewrite_prompt

PROMPT_VERSION = "v1"

# A figure: digits, with the thousands and decimals a Spanish listing writes ("1.350", "65,5").
_FIGURE = re.compile(r"\d+(?:[.,]\d+)*")
_PLACEHOLDER = re.compile(r"\[[^\]]*\]")


class RewrittenListing(BaseModel):
    """What the model fills."""

    rewritten_text: str = Field(description="El anuncio corregido, completo")
    changes: list[str] = Field(description="Una línea por cambio: qué se ha cambiado y por qué")
    placeholders: list[str] = Field(
        default_factory=list, description="Los datos que faltan y se han dejado entre corchetes"
    )


@dataclass(frozen=True)
class Rewrite:
    text: str
    changes: list[str]
    placeholders: list[str] = field(default_factory=list)
    # Figures in the rewrite that the original listing does not state: possible inventions.
    new_figures: list[str] = field(default_factory=list)
    usage: LLMUsage | None = None


def new_figures(rewritten: str, listing: Listing) -> list[str]:
    """Figures the rewrite states and the listing does not, placeholders aside."""
    stated = {_normal(figure) for figure in _FIGURE.findall(listing.as_text())}
    outside_placeholders = _PLACEHOLDER.sub(" ", rewritten)
    return list(dict.fromkeys(f for f in _FIGURE.findall(outside_placeholders) if _normal(f) not in stated))


def _normal(figure: str) -> str:
    return figure.replace(".", "").replace(",", ".")


async def rewrite_listing(
    listing: Listing, findings: list[Finding], llm: StructuredLLM, *, prompt_version: str = PROMPT_VERSION
) -> Rewrite | None:
    """None when there is nothing to fix: no rewrite is paid for a listing without findings."""
    if not findings:
        return None
    system, user = render_agent_rewrite_prompt(listing, findings, version=prompt_version)
    completion = await llm.complete_structured(system=system, user=user, schema=RewrittenListing)
    rewritten = completion.output
    return Rewrite(
        text=rewritten.rewritten_text,
        changes=rewritten.changes,
        placeholders=rewritten.placeholders,
        new_figures=new_figures(rewritten.rewritten_text, listing),
        usage=completion.usage,
    )
