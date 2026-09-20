from decimal import Decimal

import pytest
from jinja2 import TemplateNotFound, UndefinedError

from app.domain.schemas.listing_review import Listing
from app.foundation.prompts.loader import _env, render_listing_review_prompt


def test_renders_the_checklist_in_the_system_prompt() -> None:
    system, _ = render_listing_review_prompt(Listing(text="Piso en alquiler"))

    assert "RD 390/2021 art. 15.2" in system
    assert "LAU art. 36.1" in system
    assert "LAU art. 20.1" in system
    assert "Ley 12/2023 art. 31" in system


def test_renders_the_listing_in_the_user_prompt() -> None:
    listing = Listing(
        text="Piso exterior de 2 habitaciones",
        price_eur_month=Decimal("1200"),
        usable_surface_m2=Decimal("58"),
        rooms=2,
        municipality="Madrid",
        energy_rating="E",
    )

    _, user = render_listing_review_prompt(listing)

    assert "Piso exterior de 2 habitaciones" in user
    assert "1200 €/mes" in user
    assert "58 m²" in user
    assert "Madrid" in user


def test_says_which_optional_fields_are_missing() -> None:
    _, user = render_listing_review_prompt(Listing(text="Piso en alquiler"))

    assert "Precio: no indicado" in user
    assert "Calificación energética: no indicada" in user


def test_fails_when_the_version_does_not_exist() -> None:
    with pytest.raises(TemplateNotFound):
        render_listing_review_prompt(Listing(text="Piso"), version="v99")


def test_fails_when_a_template_variable_is_missing() -> None:
    template = _env.from_string("{{ listing.text }}")

    with pytest.raises(UndefinedError):
        template.render()
