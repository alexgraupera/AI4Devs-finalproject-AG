from app.foundation.text import appears_in, fold

LISTING = "Estudio de 38 m² útiles en Gràcia, amueblado. Honorarios de agencia a cargo del propietario."


def test_folding_ignores_case_accents_and_punctuation() -> None:
    assert fold("Gràcia, ¡AMUEBLADO!") == "gracia amueblado"


def test_a_literal_quote_appears() -> None:
    assert appears_in("Honorarios de agencia a cargo del propietario", LISTING)


def test_a_quote_copied_with_small_slips_still_appears() -> None:
    assert appears_in("honorarios de la agencia a cargo del propietario", LISTING)


def test_an_invented_quote_does_not_appear() -> None:
    # The Barcelona error of #40: a violation the listing says the opposite of.
    assert not appears_in("Los honorarios de agencia los paga el inquilino", LISTING)


def test_an_empty_quote_proves_nothing() -> None:
    assert not appears_in("", LISTING)
