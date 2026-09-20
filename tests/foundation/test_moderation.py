import pytest

from app.foundation.guardrails.moderation import DisabledModeration, LiteLLMModeration


class Result:
    def __init__(self, flagged: bool) -> None:
        self.flagged = flagged


class Response:
    def __init__(self, flagged: bool) -> None:
        self.results = [Result(flagged)]


async def test_reports_what_the_provider_says(monkeypatch: pytest.MonkeyPatch) -> None:
    async def flagged(**kwargs: object) -> Response:
        return Response(flagged=True)

    monkeypatch.setattr("app.foundation.guardrails.moderation.amoderation", flagged)

    assert await LiteLLMModeration().is_flagged("texto") is True


async def test_lets_the_review_through_when_moderation_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    async def broken(**kwargs: object) -> Response:
        raise RuntimeError("moderation is down")

    monkeypatch.setattr("app.foundation.guardrails.moderation.amoderation", broken)

    assert await LiteLLMModeration().is_flagged("texto") is False


async def test_disabled_moderation_flags_nothing() -> None:
    assert await DisabledModeration().is_flagged("texto") is False
