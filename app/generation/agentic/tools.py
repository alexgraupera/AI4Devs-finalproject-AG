"""The agent's tools: what each one is told, and what each one does.

Two halves per tool, as in the session on agents: a **description** the model reads (a prompt, and
written like one) and an **implementation** that runs here, in our code, when the model asks. The
model only ever produces a request; nothing runs because a model said so.

A tool never raises into the loop. A wrong argument, an empty result or a failure comes back as a
`ToolResult` the model can read, so it can correct itself instead of the run ending in an error.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.domain.schemas.listing_review import Listing
from app.foundation.llm.tools import ToolSpec
from app.generation.agentic.ports import RegulationFragment, RegulationSearch

JURISDICTIONS = {"state": "normativa estatal", "catalonia": "normativa de Cataluña"}
MAX_QUERY_CHARS = 300
FRAGMENT_CHARS = 1_500


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    # What the model reads back.
    content: str
    # What the conductor reads: the fragments behind a citation, never the model's prose.
    data: dict[str, Any] = field(default_factory=dict)


class Tool(Protocol):
    spec: ToolSpec

    async def run(self, arguments: dict[str, Any]) -> ToolResult: ...


# ── check_listing_fields ─────────────────────────────────────────────────────────────────────

MANDATORY_FIELDS = {
    "price_eur_month": "el precio mensual",
    "usable_surface_m2": "la superficie útil",
    "rooms": "el número de habitaciones",
    "municipality": "el municipio",
    "energy_rating": "la calificación energética",
}

# "950 €/mes", "950 euros al mes", "1.200 € mensuales": a rent stated in the text.
_RENT_IN_TEXT = re.compile(
    r"(\d{1,3}(?:[.\s]\d{3})+|\d+)(?:,\d+)?\s*(?:€|euros?)\s*(?:/\s*mes|al\s+mes|mensuales|mes)", re.IGNORECASE
)
# "65 m²", "65 m2", "65 metros": a surface stated in the text.
_SURFACE_IN_TEXT = re.compile(r"(\d{1,4})(?:,\d+)?\s*(?:m²|m2|metros)", re.IGNORECASE)


def _number(raw: str) -> float:
    return float(re.sub(r"[.\s]", "", raw))


class CheckListingFields:
    """Mandatory fields and internal contradictions, in code.

    Deterministic on purpose: which fields are empty and whether the text contradicts them is a
    closed, exact question, and asking a model to count them is paying tokens for a worse answer.
    It reads the listing under review rather than an argument, so the model cannot check a
    different listing from the one it was given.
    """

    spec = ToolSpec(
        name="check_listing_fields",
        description=(
            "Comprueba, sin interpretar nada, qué datos obligatorios le faltan al anuncio que estás "
            "revisando (precio, superficie útil, habitaciones, municipio, calificación energética) y "
            "si el texto contradice los datos estructurados (un precio o una superficie distintos). "
            "Llámala una vez, al empezar. No necesita argumentos."
        ),
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
    )

    def __init__(self, listing: Listing) -> None:
        self._listing = listing

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        missing = [label for name, label in MANDATORY_FIELDS.items() if getattr(self._listing, name) in (None, "")]
        contradictions = self._contradictions()

        lines = []
        lines.append("Faltan: " + ", ".join(missing) + "." if missing else "No falta ningún dato obligatorio.")
        lines += contradictions or ["El texto no contradice los datos estructurados."]
        return ToolResult(
            ok=True, content="\n".join(lines), data={"missing": missing, "contradictions": contradictions}
        )

    def _contradictions(self) -> list[str]:
        found = []
        price = self._listing.price_eur_month
        if price is not None:
            stated = [_number(match.group(1)) for match in _RENT_IN_TEXT.finditer(self._listing.text)]
            if stated and all(abs(value - float(price)) > float(price) * 0.01 for value in stated):
                found.append(f"El texto indica un alquiler de {stated[0]:g} € al mes y el campo precio dice {price} €.")
        surface = self._listing.usable_surface_m2
        if surface is not None:
            stated = [_number(match.group(1)) for match in _SURFACE_IN_TEXT.finditer(self._listing.text)]
            if stated and all(abs(value - float(surface)) > float(surface) * 0.05 for value in stated):
                found.append(f"El texto indica {stated[0]:g} m² y el campo superficie útil dice {surface} m².")
        return found


# ── search_regulations ───────────────────────────────────────────────────────────────────────


class SearchRegulations:
    """The RAG layer, as a tool. The fragments it returns are the only ones a finding may cite."""

    spec = ToolSpec(
        name="search_regulations",
        description=(
            "Busca en la normativa española de alquiler indexada: Ley 29/1994 de Arrendamientos "
            "Urbanos, Ley 12/2023 por el derecho a la vivienda, Real Decreto 390/2021 del certificado "
            "energético, Ley 18/2007 del derecho a la vivienda de Cataluña y las declaraciones de zonas "
            "tensionadas. Devuelve fragmentos numerados [n]; cita esos números en `sources`. Haz una "
            "búsqueda por tema (fianza, honorarios, etiqueta energética...), con las palabras de la "
            "ley mejor que con las del anuncio. Si no devuelve nada, reformula una vez; si sigue sin "
            "nada, la normativa indexada no lo cubre."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Qué buscar, en español, en pocas palabras"},
                "jurisdictions": {
                    "type": "array",
                    "items": {"type": "string", "enum": list(JURISDICTIONS)},
                    "description": "Limita la búsqueda: ['catalonia'] para un piso en Cataluña. Omítelo para todas",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    )

    def __init__(self, search: RegulationSearch, *, max_fragments: int = 5) -> None:
        self._search = search
        self._max_fragments = max_fragments

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        query = arguments.get("query")
        if not isinstance(query, str) or not query.strip():
            return ToolResult(ok=False, content="Falta `query`: di qué quieres buscar.")
        if len(query) > MAX_QUERY_CHARS:
            return ToolResult(
                ok=False, content=f"`query` es demasiado larga: usa menos de {MAX_QUERY_CHARS} caracteres."
            )

        jurisdictions = arguments.get("jurisdictions")
        if jurisdictions is not None and (
            not isinstance(jurisdictions, list) or any(value not in JURISDICTIONS for value in jurisdictions)
        ):
            return ToolResult(ok=False, content=f"`jurisdictions` solo admite {list(JURISDICTIONS)}.")

        fragments = (await self._search.search_regulations(query.strip(), jurisdictions=jurisdictions or None))[
            : self._max_fragments
        ]
        if not fragments:
            return ToolResult(
                ok=True,
                content="No hay fragmentos de la normativa indexada para esa búsqueda.",
                data={"fragments": []},
            )
        return ToolResult(
            ok=True, content="\n\n".join(_render(fragment) for fragment in fragments), data={"fragments": fragments}
        )


def _render(fragment: RegulationFragment) -> str:
    scope = JURISDICTIONS.get(fragment.jurisdiction, fragment.jurisdiction)
    text = fragment.text if len(fragment.text) <= FRAGMENT_CHARS else fragment.text[:FRAGMENT_CHARS] + " [...]"
    return f"[{fragment.chunk_id}] {fragment.law_title} · {fragment.article_title} ({scope})\n{text}"
