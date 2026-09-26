from decimal import Decimal
from typing import TypeVar

from pydantic import BaseModel

from app.domain.schemas.listing_review import Finding, FindingCategory, Listing, Severity
from app.foundation.llm.usage import LLMUsage, StructuredCompletion
from app.generation.agentic.rewrite import RewrittenListing, new_figures, rewrite_listing

T = TypeVar("T", bound=BaseModel)

A_LISTING = Listing(
    text="Piso de 65 m² en Chamberí. 1.350 €/mes. Se piden dos meses de fianza.", price_eur_month=Decimal(1350)
)
A_FINDING = Finding(
    category=FindingCategory.DEPOSIT_AND_GUARANTEES,
    severity=Severity.HIGH,
    message="La fianza supera una mensualidad",
    suggestion="Pide una mensualidad de fianza",
    legal_basis="LAU art. 36.1",
)


class ScriptedWriter:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = 0
        self.user: str | None = None

    async def complete_structured(self, *, system: str, user: str, schema: type[T]) -> StructuredCompletion[T]:
        self.calls += 1
        self.user = user
        output = RewrittenListing(
            rewritten_text=self.text,
            changes=["Fianza ajustada a una mensualidad"],
            placeholders=["calificación energética"],
        )
        usage = LLMUsage("openai", "gpt-5.4-mini", 900, 200, 800, Decimal("0.0016"))
        return StructuredCompletion(output=output, usage=usage)  # type: ignore[arg-type]


async def test_rewrites_the_listing_for_its_findings() -> None:
    writer = ScriptedWriter(
        "Piso de 65 m² en Chamberí. 1.350 €/mes. Fianza de una mensualidad. [indica la calificación energética]"
    )

    rewrite = await rewrite_listing(A_LISTING, [A_FINDING], writer)

    assert rewrite is not None
    assert rewrite.changes == ["Fianza ajustada a una mensualidad"]
    assert rewrite.placeholders == ["calificación energética"]
    assert rewrite.new_figures == []
    assert writer.user is not None and "Pide una mensualidad de fianza" in writer.user


async def test_nothing_to_fix_means_no_rewrite_and_no_call() -> None:
    writer = ScriptedWriter("")

    assert await rewrite_listing(A_LISTING, [], writer) is None
    assert writer.calls == 0


async def test_a_figure_the_listing_never_stated_is_reported() -> None:
    # The one thing a rewrite must never do: a compliant listing that is false.
    writer = ScriptedWriter(
        "Piso de 70 m² en Chamberí. 1.350 €/mes. Fianza de una mensualidad. Certificado energético B."
    )

    rewrite = await rewrite_listing(A_LISTING, [A_FINDING], writer)

    assert rewrite is not None and rewrite.new_figures == ["70"]


def test_figures_inside_a_placeholder_are_not_inventions() -> None:
    assert new_figures("65 m². [indica la superficie en m², por ejemplo 70]", A_LISTING) == []


def test_figures_are_compared_the_way_a_listing_writes_them() -> None:
    assert new_figures("Precio: 1350 € al mes", A_LISTING) == []
